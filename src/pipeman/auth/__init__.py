import flask_login
from autoinject import injector
from pipeman.util import System
from .auth import AuthenticationManager, AuthenticatedUser, require_permission
from .secure import SecurityHelper
import flask


@injector.inject
def auth_init_app(app, am: AuthenticationManager):
    lm = flask_login.LoginManager()
    lm.init_app(app)
    lm.login_view = "auth.login"
    lm.user_loader(am.load_user)
    lm.request_loader(am.login_from_request)
    lm.unauthorized_handler(am.unauthorized_handler)
    lm.anonymous_user = am.anonymous_user

    @app.before_request
    def set_session_vars():
        flask.session.permanent = True
        flask.session.modified = True


def init(system: System):
    system.register_init_app(auth_init_app)
    system.register_blueprint("pipeman.auth.app", "auth")
    system.register_cli("pipeman.auth.cli", "group")
