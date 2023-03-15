import flask
import pathlib
import sys
from autoinject import injector

sys.path.append(str(pathlib.Path(__file__).parent / "src"))

from pipeman.util import System
from pipeman.init import init as pipeman_init


@injector.inject
def create_app(reg: System = None):
    _app = flask.Flask(__name__)
    reg.init_app(_app)
    return _app


pipeman_init(extra_files=["./.pipeman.flask.toml", "~/.pipeman.flask.toml"])
app = create_app()

