import flask_login
from autoinject import injector
from pipeman.util import System
from .auth import AuthenticationManager, AuthenticatedUser, require_permission
from pipeman.db import Database
import pipeman.db.orm as orm
import sqlalchemy as sa
from .secure import SecurityHelper
from pipeman.util.errors import UserInputError
import datetime
import flask
import zrlog
import os
import zirconium as zr


@injector.inject
def auth_init_app(app: flask.Flask, am: AuthenticationManager):
    """Initialize the Flask application for authentication management."""
    # Initialize the flask_login LoginManager
    lm = flask_login.LoginManager()
    # Strong session protection is necessary
    lm.session_protection = 'strong'
    # Call init_app() for the login manager
    lm.init_app(app)
    # Configure the login manager to delegate to the AuthenticationManager
    lm.login_view = "auth.login"
    lm.user_loader(am.load_user)
    lm.request_loader(am.login_from_request)
    lm.unauthorized_handler(am.unauthorized_handler)
    lm.anonymous_user = am.anonymous_user


def init(system: System):
    """Initialize authentication-related systems."""
    system.on_app_init(auth_init_app)
    system.register_blueprint("pipeman.auth.app", "auth")
    system.register_cli("pipeman.auth.cli", "group")
    system.on_setup(_do_setup)
    system.on_cleanup(_do_cleanup)
    system.on_cron_start(_register_cron)


def _register_cron(cron):
    cron.register_periodic_job("cleanup_login_records", _do_cleanup, days=1)


def _do_setup():
    admin_group = os.environ.get("PIPEMAN_ADMIN_GROUP", "superuser")
    zrlog.get_logger("pipeman.auth").info(f"Creating admin group {admin_group}")
    from .util import create_group, grant_permission
    try:
        create_group(admin_group, {'und': 'Administrators'})
    except UserInputError:
        pass
    try:
        grant_permission(admin_group, 'superuser')
    except UserInputError:
        pass


@injector.inject
def _do_cleanup(db: Database = None, config: zr.ApplicationConfig = None):
    log = zrlog.get_logger("pipeman.auth")
    with db as session:
        # Handle ServerSession objects
        dt = datetime.datetime.now()
        log.info(f"Cleaning up user sessions older than {dt}")
        q = sa.delete(orm.ServerSession).where(orm.ServerSession.valid_until < dt)
        session.execute(q)
        session.commit()

        # Handle UserLoginRecord objects
        keep_days = config.as_int(("pipeman", "authentication", "retain_login_records_days"), default=30)
        if keep_days is None or keep_days < 14:
            keep_days = 14
        dt = datetime.datetime.now() - datetime.timedelta(days=keep_days)
        log.info(f"Cleaning up user login records older than {dt}")
        q = sa.delete(orm.UserLoginRecord).where(orm.UserLoginRecord.attempt_time < dt)
        session.execute(q)
        session.commit()
