from autoinject import injector
from pipeman.util import System


@injector.inject
def init_plugin(system: System = None):
    system.register_blueprint("pipeman.builtins.mtrans.endpoints", "mtrans")
