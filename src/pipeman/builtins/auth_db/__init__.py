from pipeman.util.system import System as _System
from autoinject import injector as _injector
from .controller import DatabaseEntityAuthenticationManager


@_injector.inject
def init_plugin(system: _System):
    system.register_blueprint("pipeman.builtins.auth_db.app", "users")
    system.register_cli("pipeman.builtins.auth_db.cli", "user")
