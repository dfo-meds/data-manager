import flask_login
from autoinject import injector
from pipeman.util import System
from .auth import AuthenticationManager, AuthenticatedUser, require_permission
from .secure import SecurityHelper
from pipeman.util.errors import UserInputError
import flask
import os


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
    system.register_init_app(auth_init_app)
    system.register_blueprint("pipeman.auth.app", "auth")
    system.register_cli("pipeman.auth.cli", "group")
    system.register_setup_fn(setup)


def setup():
    admin_group = os.environ.get("PIPEMAN_ADMIN_GROUP", "superuser")
    from .util import create_group, grant_permission
    try:
        create_group(admin_group, {'und': 'Administrators'})
    except UserInputError:
        pass
    try:
        grant_permission(admin_group, 'superuser')
    except UserInputError:
        pass
