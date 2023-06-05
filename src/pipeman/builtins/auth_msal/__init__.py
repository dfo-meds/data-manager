from pipeman.util.system import System as _System
from autoinject import injector as _injector


@_injector.inject
def init_plugin(system: _System):
    #system.register_blueprint("pipeman.builtins.auth_msal.app", "bp")
    pass
