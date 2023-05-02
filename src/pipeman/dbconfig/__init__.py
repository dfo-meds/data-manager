from .controller import ValueController
from pipeman.util import System
import datetime
from autoinject import injector


def init(system: System):
    system.post_setup(_set_last_run)


@injector.inject
def _set_last_run(vc: ValueController = None):
    vc.set_value("setup_last_run", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
