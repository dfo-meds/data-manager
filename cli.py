import flask
import pathlib
import sys
from autoinject import injector

sys.path.append(str(pathlib.Path(__file__).parent / "src"))

from pipeman.util import System
from pipeman.init import init as pipeman_init


@injector.inject
def create_cli(reg: System = None):
    import flask
    _app = flask.Flask(__name__)
    return reg.init_cli(_app)


pipeman_init(extra_files=[".pipeman.cli.toml"])
app2 = create_cli()
app2()
