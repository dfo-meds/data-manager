from pipeman.util.system import System as _System
from autoinject import injector as _injector
from .controller import DatabaseEntityAuthenticationManager


@_injector.inject
def init_plugin(system: _System):
    system.register_blueprint("pipeman.builtins.auth_db.app", "users")
    system.register_cli("pipeman.builtins.auth_db.cli", "user")
    system.register_nav_item("me", "auth_db.me", "users.view_myself", "self", 'user')
    system.register_nav_item("change_password", "auth_db.change_password", "users.change_my_password", "self", 'user')
    system.register_nav_item("edit_profile", "auth_db.edit_profile", "users.edit_myself", "self", 'user')
    system.register_nav_item("users", "auth_db.list_users", "users.list_users", "auth_db.view_users")
