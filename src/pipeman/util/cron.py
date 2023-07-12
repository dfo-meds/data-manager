import datetime
import signal
from pipeman.util import System
import flask
import threading
import zirconium as zr
import zrlog
import time
from autoinject import injector
import enum


class TaskState(enum.Enum):

    EXECUTING = 2
    QUEUED = 1
    NONE = 0


class UniqueTaskThreadManager:

    def __init__(self, app, halt_event, max_threads):
        self._app = app
        self.halt = halt_event
        self._max_threads: int = max_threads
        self._queued: dict[str, callable] = {}
        self._queued_names: list[str] = []
        self._executing: dict[str, TaskThread] = {}

    def execute(self, name, callback):
        self.reap()
        if name in self._executing or name in self._queued_names:
            return
        self._queued[name] = callback
        self._queued_names.append(name)

    def job_state(self, name: str):
        if name in self._executing:
            return TaskState.EXECUTING
        if name in self._queued_names:
            return TaskState.QUEUED
        return TaskState.NONE

    def sow(self):
        self.reap()
        sow_count = min(len(self._queued_names), self._max_threads - len(self._executing))
        if sow_count > 0:
            for i in range(0, sow_count):
                self._sow(self._queued_names[i])
                if self.halt.is_set():
                    break
            self._queued_names = self._queued_names[sow_count:]

    def _sow(self, key: str):
        t = TaskThread(self._app, self.halt, self._queued[key])
        t.start()
        del self._queued[key]

    def reap(self):
        for k in self._executing:
            if self._executing[k] and self._executing[k].is_alive():
                continue
            else:
                del self._executing[k]

    def active_threads(self):
        return sum(1 if self._executing[k] and self._executing[k].is_alive() else 0 for k in self._executing)

    def wait_for_all(self, timeout=5):
        s = time.monotonic()
        check = True
        while check:
            check = False
            for k in self._executing:
                if self._executing[k] and self._executing[k].is_alive():
                    check = True
            if 0 < timeout < (time.monotonic() - s):
                check = False


class TaskThread(threading.Thread):

    def __init__(self, app, halt_event, callback):
        super().__init__()
        self._app = app
        self.halt = halt_event
        self.callback = callback

    def run(self):
        with self._app.app_context():
            self.callback(self)


class CronThread(threading.Thread):

    def __init__(self, app, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.halt = threading.Event()
        self.app = app

    def terminate(self):
        self.halt.set()

    def startup(self):
        pass

    def run(self):
        with self.app.app_context():
            self._run()

    def _run(self):
        pass

    def cleanup(self):
        pass


class PeriodicJob:

    def __init__(self, name: str, callback: callable, delay_seconds: int, off_peak_only: bool = False):
        self.name = name
        self.last_executed = None
        self.callback = callback
        self.delay_seconds = max(1, delay_seconds)
        self.off_peak_only = off_peak_only

    def check_and_execute(self, t: UniqueTaskThreadManager, now: datetime.datetime, is_peak: bool):
        if self._check_execution(t, now, is_peak):
            t.execute(self.name, self.callback)
            self.last_executed = now

    def _check_execution(self, t: UniqueTaskThreadManager, now: datetime.datetime, is_peak: bool):
        if t.job_state(self.name) != TaskState.NONE:
            return False
        if is_peak and self.off_peak_only:
            return False
        if self.last_executed is None:
            return True
        return (now - self.last_executed).total_seconds() > self.delay_seconds


class CronDaemon:

    system: System = None
    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self._app = self.system.main_app
        self.halt = threading.Event()
        self._cron_threads: dict[str, CronThread] = {}
        self._cron_thread_classes = {}
        self._periodic_jobs = {}
        self.log = zrlog.get_logger("pipeman.cron")
        self._exit_count = 0
        self._max_scheduled_tasks = self.config.as_int(("pipeman", "daemon", "max_thread_count"), default=4)
        self._max_exit_count = self.config.as_int(("pipeman", "daemon", "max_exit_count"), default=3)
        self._cleanup_sleep_time = self.config.as_float(("pipeman", "daemon", "exit_cleanup_sleep"), default=0.25)
        self._max_cleanup_time = self.config.as_int(("pipeman", "daemon", "max_cleanup_time_seconds"), default=5)
        self._tasks = UniqueTaskThreadManager(self._app, self.halt, self._max_scheduled_tasks)

    def register_cron_thread(self, cls: type, constructor: callable = None):
        self._cron_thread_classes[cls] = constructor or cls

    def register_periodic_job(self, name: str, callback: callable, seconds: int = 0, minutes: int = 0, hours: int = 0, days: int = 0, off_peak_only: bool = False):
        self._periodic_jobs[name] = PeriodicJob(callback, seconds + (minutes * 60) + (hours * 3600) + (days * 3600 * 24), off_peak_only)

    def _exit_signal_handler(self, signum, frame):
        self.log.debug(f"Received signal {signum}, attempting to halt")
        self.halt.set()
        self._exit_count += 1
        if self._exit_count >= self._max_exit_count:
            self.log.warning(f"Max exit count exceeded, crashing")
            raise KeyboardInterrupt()

    def register_exit_signal(self, sig_name: str):
        if hasattr(signal, sig_name):
            self.log.debug(f"Registering signal {sig_name} to exit on")
            signal.signal(getattr(signal, sig_name), self._exit_signal_handler)

    def run_forever(self):
        self._setup()
        try:
            while not self.halt.is_set():
                self._inner_loop()
                self.halt.wait(0.25)
        finally:
            self.log.debug("Cleaning up...")
            self._cleanup()

    def _setup(self):
        self.log.debug("Starting cron manager...")
        self.register_exit_signal("SIGBREAK")
        self.register_exit_signal("SIGINT")
        self.register_exit_signal("SIGTERM")
        self.system.fire("cron.start.before", self)
        self.system.fire("cron.start", self)
        self.system.fire("cron.start.after", self)

    def _inner_loop(self):
        now = datetime.datetime.now()
        is_peak = self.is_peak_hours(now)
        for k in self._cron_thread_classes:
            if k not in self._cron_threads:
                self._start_thread(k)
            elif not self._cron_threads[k].is_alive():
                if hasattr(self._cron_threads[k], "cleanup"):
                    self.log.info(f"Cleaning up completed thread {k}")
                    self._cron_threads[k].cleanup()
                self._start_thread(k)
        for k in self._periodic_jobs:
            self._periodic_jobs[k].check_and_execute(self._tasks, now, is_peak)
        self.system.fire("cron.before", self)
        self.system.fire("cron", self)
        self.system.fire("cron.after", self)

    def is_peak_hours(self, now: datetime.datetime):
        day_of_week = now.weekday()
        weekends = self.config.as_list(("pipeman", "cron", "weekend_days"), [5, 6])
        if day_of_week in weekends:
            return False
        work_day_start = self.config.as_int(("pipeman", "cron", "workday_start"), 6)
        work_day_end = self.config.as_int(("pipeman", "cron", "workday_end"), 18)
        if work_day_start > work_day_end:
            return work_day_start <= now.hour < work_day_end
        elif work_day_start < work_day_end:
            return now.hour >= work_day_start or now.hour < work_day_end
        return True

    def _start_thread(self, k):
        self._cron_threads[k] = self._cron_thread_classes[k](self._app)
        if not hasattr(self._cron_threads[k], "halt"):
            raise ValueError(f"Cron threads must declare a halt() method to wrap them up")
        if not hasattr(self._cron_threads[k], "join"):
            raise ValueError(f"Cron threads must subclass threading.Thread")
        self.log.info(f"Starting thread {k}")
        self._cron_threads[k].startup()
        self._cron_threads[k].start()

    def _cleanup(self):
        self.system.fire("cron.stop.before", self)
        cleanup_start = time.monotonic()
        self.halt.set()
        for k in self._cron_threads:
            if self._cron_threads[k] and self._cron_threads[k].is_alive():
                self._cron_threads[k].terminate()
        keep_checking = True
        while keep_checking:
            keep_checking = False
            count = 0
            for k in self._cron_threads:
                if self._cron_threads[k] and self._cron_threads[k].is_alive():
                    count += 1
            count += self._tasks.active_threads()
            if count > 0:
                keep_checking = (time.monotonic() - cleanup_start) < self._max_cleanup_time
                if keep_checking:
                    self.log.notice(f"{count} threads still active, waiting for them to complete")
                    time.sleep(self._cleanup_sleep_time)
                else:
                    self.log.warning(f"{count} threads still active, some data loss may occur!")
            else:
                self.log.notice("All threads completed, exiting")
        self.system.fire("cron.stop", self)
        self.system.fire("cron.stop.after", self)
