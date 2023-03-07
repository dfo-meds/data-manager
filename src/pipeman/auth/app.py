import flask
import flask_login as fl
from autoinject import injector
from pipeman.auth.auth import AuthenticationManager
from pipeman.util.flask import MultiLanguageBlueprint

auth = MultiLanguageBlueprint("auth", __name__)


@auth.i18n_route("/login", methods=["GET", "POST"])
@injector.inject
def login(am: AuthenticationManager = None):
    if fl.current_user.is_authenticated:
        return am.login_success()
    return am.login_handler()


@auth.i18n_route("/logout", methods=["GET", "POST"])
@injector.inject
def logout(am: AuthenticationManager = None):
    if not fl.current_user.is_authenticated:
        return am.logout_success()
    return am.logout_handler()


@auth.i18n_route("/api/refresh", methods=['GET'])
def refresh_session():
    return {}


# TODO: add group controls here?
