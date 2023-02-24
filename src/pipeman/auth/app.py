import flask
import flask_login as fl
from autoinject import injector
from pipeman.auth.auth import AuthenticationManager

auth = flask.Blueprint("auth", __name__)


@auth.route("/login", methods=["GET", "POST"])
@injector.inject
def login(am: AuthenticationManager = None):
    if fl.current_user.is_authenticated:
        return am.login_success()
    return am.login_handler()


@auth.route("/logout", methods=["GET", "POST"])
@injector.inject
def logout(am: AuthenticationManager = None):
    if not fl.current_user.is_authenticated:
        return am.logout_success()
    return am.logout_handler()


@auth.route("/refresh", methods=['GET'])
def refresh_session():
    pass


# TODO: add group controls here?
