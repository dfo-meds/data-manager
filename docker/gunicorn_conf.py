from __future__ import print_function

import multiprocessing
import os

from prometheus_client.multiprocess import mark_process_dead


def child_exit(server, worker):
    mark_process_dead(worker.pid)


def worker_exit(server, worker):
    from pipeman.db import on_gunicorn_worker_exit
    on_gunicorn_worker_exit()


# Load defaults from environment
workers_per_core_str = int(os.getenv("WORKERS_PER_CORE", 2))
web_concurrency_str = os.getenv("WEB_CONCURRENCY", None)
worker_class = os.getenv("WORKER_CLASS", "gevent")
worker_connections = int(os.getenv("WORKER_CONNECTIONS", 1000))
max_requests = int(os.getenv("WORKER_MAX_REQUESTS", 5000))
max_requests_jitter = int(os.getenv("WORKER_MAX_REQUESTS_JITTER", 10))
timeout = int(os.getenv("REQUEST_TIMEOUT", 30))
keepalive = int(os.getenv("KEEPALIVE", 15))
host = os.getenv("HOST", "0.0.0.0")
port = os.getenv("PORT", "80")
bind_env = os.getenv("BIND", None)
errorlog = os.getenv("ERROR_LOG", "-")
accesslog = os.getenv("ACCESS_LOG", None)
loglevel = os.getenv("LOG_LEVEL", "info")
enable_stdio_inheritance = os.getenv("ENABLE_STDIO_INHERITANCE", "1") == "1"

# Set use_bind
if bind_env:
    bind = bind_env
else:
    bind = "{host}:{port}".format(host=host, port=port)

cores = multiprocessing.cpu_count()
# Set number of workers as needed
if web_concurrency_str:
    workers = int(web_concurrency_str)
else:
    workers_per_core = float(workers_per_core_str)
    default_web_concurrency = (workers_per_core * cores) + 1
    workers = int(default_web_concurrency)
assert workers > 0
assert worker_class in ('sync', 'eventlet', 'gevent', 'tornado', 'gthread')

if os.getenv("DUMP_GUNICORN_CONFIG", "1") == "1":
    # For debugging and testing
    log_data = {
        "loglevel": loglevel,
        "workers": workers,
        "worker_class": worker_class,
        "worker_connections": worker_connections,
        "max_requests": max_requests,
        "max_requests_jitter": max_requests_jitter,
        "keepalive": keepalive,
        "bind": bind,
        "enable_stdio_inheritance": enable_stdio_inheritance,
        "accesslog": accesslog,
        "errorlog": errorlog,
        "timeout": timeout,
        "_host": host,
        "_port": port,
        "_fixed_web_concurrency": web_concurrency_str,
        "_cpu_count": cores,
        "_workers_per_core": workers_per_core_str,
    }
    print("gunicorn config::")
    pad = max(len(x) for x in log_data) + 5
    for x in log_data:
        print(f"{x.ljust(pad)} {log_data[x]}")
