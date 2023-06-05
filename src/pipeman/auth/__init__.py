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
from .controller import DatabaseUserController


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
    lm.unauthorized_handler(am.unauthorized)
    lm.anonymous_user = am.anonymous_user
    if 'csrf' in app.extensions:
        app.extensions['csrf'].exempt('pipeman.auth.app.login_by_redirect')


def init(system: System):
    """Initialize authentication-related systems."""
    system.on_app_init(auth_init_app)
    system.register_blueprint("pipeman.auth.app", "auth")
    system.register_cli("pipeman.auth.cli", "group")
    system.on_setup(_do_setup)
    system.on_cleanup(_do_cleanup)
    system.on_cron_start(_register_cron)
    system.register_blueprint("pipeman.auth.app", "users")
    system.register_cli("pipeman.auth.cli", "user")
    system.register_nav_item("me", "auth_db.me", "users.view_myself", "_is_not_anonymous", 'user')
    system.register_nav_item("change_password", "auth_db.change_password", "users.change_my_password", "_is_not_anonymous", 'user')
    system.register_nav_item("edit_profile", "auth_db.edit_profile", "users.edit_myself", "_is_not_anonymous", 'user')
    system.register_nav_item("users", "auth_db.list_users", "users.list_users", "auth_db.view.all", weight=100000000)
    system.on_setup(setup_plugin)


@injector.inject
def setup_plugin(duc: DatabaseUserController = None):
    zrlog.get_logger("pipeman.auth").info("Creating admin account")
    username = os.environ.get("PIPEMAN_ADMIN_USERNAME", "admin")
    password = os.environ.get("PIPEMAN_ADMIN_PASSWORD", "PasswordPassword")
    display = os.environ.get("PIPEMAN_ADMIN_DISPLAY", "Administrator")
    email = os.environ.get("PIPEMAN_ADMIN_EMAIL", "admin@example.com")
    admin_group = os.environ.get("PIPEMAN_ADMIN_GROUP", "superuser")
    try:
        duc.create_user_cli(username, email, display, password)
    except UserInputError as ex:
        pass
    try:
        duc.assign_to_group_cli(admin_group, username)
    except UserInputError as ex:
        pass


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
def _do_cleanup(st=None, db: Database = None, config: zr.ApplicationConfig = None):
    log = zrlog.get_logger("pipeman.auth")
    with db as session:
        # Handle ServerSession objects
        dt = datetime.datetime.now()
        log.info(f"Cleaning up user sessions older than {dt}")
        q = sa.delete(orm.ServerSession).where(orm.ServerSession.valid_until < dt)
        session.execute(q)
        session.commit()
        if st and st.halt.is_set():
            return
        # Handle UserLoginRecord objects
        keep_days = config.as_int(("pipeman", "authentication", "retain_login_records_days"), default=30)
        if keep_days is None or keep_days < 14:
            keep_days = 14
        dt = datetime.datetime.now() - datetime.timedelta(days=keep_days)
        log.info(f"Cleaning up user login records older than {dt}")
        q = sa.delete(orm.UserLoginRecord).where(orm.UserLoginRecord.attempt_time < dt)
        session.execute(q)
        session.commit()
