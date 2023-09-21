from .db import Database, DatabasePool
from .obj_registry import BaseObjectRegistry
from autoinject import injector as _injector


@_injector.inject
def on_gunicorn_worker_exit(db_pool: DatabasePool):
    db_pool.close()
