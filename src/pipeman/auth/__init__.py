import flask_login
from autoinject import injector
from pipeman.util import System
from pipeman.auth.auth import AuthenticationManager


@injector.inject
def auth_init_app(app, am: AuthenticationManager):
    lm = flask_login.LoginManager()
    lm.init_app(app)
    lm.login_view = "auth.login"
    lm.user_loader(am.load_user)
    lm.request_loader(am.login_from_request)
    lm.anonymous_user = am.anonymous_user


def init(system: System):
    system.register_init_app(auth_init_app)
    system.register_blueprint("pipeman.auth.app", "auth")
