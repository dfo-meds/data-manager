import time
import os
import prometheus_client as pc
import prometheus_client.multiprocess as pcmp
from prometheus_flask_exporter import PrometheusMetrics
from autoinject import injector
import threading
import functools
import logging


@injector.injectable_global
class PromMetrics:

    def __init__(self):
        self.metrics = None
        self.stats = {}
        self._lock = threading.RLock()
        self.log = logging.getLogger(__name__)
        self.collector = None

    def init_app(self, app):
        if self.metrics is None:
            reg = pc.CollectorRegistry()
            if os.environ.get("PROMETHEUS_MULTIPROC_DIR", default=None):
                self.collector = pcmp.MultiProcessCollector(reg)
            else:
                self.log.warning("PROMETHEUS_MULTIPROC_DIR not set, Prometheus metrics may be corrupt if using a multi-process WSGI server")
            self.metrics = PrometheusMetrics(app, registry=reg)

    def get_stat(self, name, documentation, cls):
        if name not in self.stats:
            with self._lock:
                if name not in self.stats:
                    self.stats[name] = cls(name, documentation)
        return self.stats[name]


class BlockTimer:

    metrics: PromMetrics = None

    @injector.construct
    def __init__(self, name, documentation):
        self._metric = self.metrics.get_stat(name, documentation, pc.Summary)
        self._start = None

    def __enter__(self):
        self._start = time.monotonic()

    def __exit__(self, a, b, c):
        self._metric.observe(time.monotonic() - self._start)
        self._start = None


def time_function(name, documentation):
    def _wrapper(fn):

        @functools.wraps(fn)
        def _inner_wrapper(*args, **kwargs):
            with BlockTimer(name, documentation):
                return fn(*args, **kwargs)
        return _inner_wrapper

    return _wrapper