from pipeman.db import Database
import pipeman.db.orm as orm
from autoinject import injector
import datetime
import signal
from pipeman.util import System
import threading
import zirconium as zr
import zrlog


@injector.inject
def user_list(db: Database = None):
    with db as session:
        users = []
        for user in session.query(orm.User):
            users.append((user.id, user.display))
        return users


class CronThread(threading.Thread):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._halt = threading.Event()

    def terminate(self):
        self._halt.set()

    def startup(self):
        pass

    def cleanup(self):
        pass


class PeriodicJob:

    def __init__(self, callback: callable, delay_seconds: int, off_peak_only: bool = False):
        self.last_executed = None
        self.callback = callback
        self.delay_seconds = max(1, delay_seconds)
        self.off_peak_only = off_peak_only

    def check_and_execute(self, now: datetime.datetime):
        if self._check_execution(now):
            self.callback()
            self.last_executed = now

    def _check_execution(self, now):
        if self.last_executed is None:
            return True
        return (now - self.last_executed).total_seconds() > self.delay_seconds


class CronDaemon:

    system: System = None
    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self.halt = threading.Event()
        self._cron_threads: dict[str, CronThread] = {}
        self._cron_thread_classes = {}
        self._periodic_jobs = {}
        self.log = zrlog.get_logger("pipeman.cron")
        self._exit_count = 0
        self._max_exit_count = self.config.as_int(("pipeman", "daemon", "max_exit_count"), default=3)

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
            if is_peak and self._periodic_jobs[k].off_peak_only:
                continue
            # TODO: worth considering doing this in a thread or something so we can kill it?
            self._periodic_jobs[k].check_and_execute(now)
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
        self._cron_threads[k] = self._cron_thread_classes[k]()
        if not hasattr(self._cron_threads[k], "halt"):
            raise ValueError(f"Cron threads must declare a halt() method to wrap them up")
        if not hasattr(self._cron_threads[k], "join"):
            raise ValueError(f"Cron threads must subclass threading.Thread")
        self.log.info(f"Starting thread {k}")
        self._cron_threads[k].startup()
        self._cron_threads[k].start()

    def _cleanup(self):
        self.system.fire("cron.stop.before", self)
        for k in self._cron_threads:
            self._cron_threads[k].terminate()
            # TODO: this might hang forever, what do we do?
            self._cron_threads[k].join()
        self.system.fire("cron.stop", self)
        self.system.fire("cron.stop.after", self)
