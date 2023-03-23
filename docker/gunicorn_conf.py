from __future__ import print_function

import json
import multiprocessing
import os

workers_per_core_str = os.getenv("WORKERS_PER_CORE", "2")
web_concurrency_str = os.getenv("WEB_CONCURRENCY", None)
worker_class = os.getenv("WORKER_CLASS", "gevent")
worker_connections = os.getenv("WORKER_CONNECTIONS", 1000)
max_requests = os.getenv("WORKER_MAX_REQUESTS", 5000)
max_requests_jitter = 10
host = os.getenv("HOST", "0.0.0.0")
port = os.getenv("PORT", "80")
bind_env = os.getenv("BIND", None)
use_loglevel = os.getenv("LOG_LEVEL", "info")
if bind_env:
    use_bind = bind_env
else:
    use_bind = "{host}:{port}".format(host=host, port=port)

cores = multiprocessing.cpu_count()
workers_per_core = float(workers_per_core_str)
default_web_concurrency = (workers_per_core * cores) + 1
if web_concurrency_str:
    web_concurrency = int(web_concurrency_str)
    assert web_concurrency > 0
else:
    web_concurrency = int(default_web_concurrency)

# Gunicorn config variables
loglevel = use_loglevel
bind = use_bind
keepalive = 120
errorlog = "-"
accesslog = "-"
keepalive = 15

# For debugging and testing
log_data = {
    "loglevel": loglevel,
    "workers": web_concurrency,
    "worker_class": worker_class,
    "worker_connections": worker_connections,
    "max_requests": max_requests,
    "max_requests_jitter": max_requests_jitter,
    "keepalive": keepalive,
    "bind": bind,
    # Additional, non-gunicorn variables
    "workers_per_core": workers_per_core,
    "host": host,
    "port": port,
}
print(json.dumps(log_data))
