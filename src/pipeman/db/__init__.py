from .db import Database
from .obj_registry import BaseObjectRegistry
from autoinject import injector as _injector


@_injector.inject
def on_gunicorn_worker_exit(db: Database):
    db.close()
