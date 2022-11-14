import flask
from autoinject import injector
from pipeman.util.system import System

auth = flask.Blueprint("auth", __name__)


@injector.inject
def login(reg: System = None):
    return reg.globals["authenticator"].login_handler()


@injector.inject
def logout(reg: System = None):
    return reg.globals["authenticator"].logout_handler()
