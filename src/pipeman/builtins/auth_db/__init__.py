from pipeman.util.system import System as _System
from autoinject import injector as _injector
from .controller import DatabaseEntityAuthenticationManager, DatabaseUserController
from pipeman.util.errors import UserInputError
import os


@_injector.inject
def init_plugin(system: _System):
    system.register_blueprint("pipeman.builtins.auth_db.app", "users")
    system.register_cli("pipeman.builtins.auth_db.cli", "user")
    system.register_nav_item("me", "auth_db.me", "users.view_myself", "self", 'user')
    system.register_nav_item("change_password", "auth_db.change_password", "users.change_my_password", "self", 'user')
    system.register_nav_item("edit_profile", "auth_db.edit_profile", "users.edit_myself", "_is_not_anonymous", 'user')
    system.register_nav_item("users", "auth_db.list_users", "users.list_users", "auth_db.view_users", weight=100000000)
    system.register_setup_fn(setup_plugin)


@_injector.inject
def setup_plugin(duc: DatabaseUserController):
    username = os.environ.get("PIPEMAN_ADMIN_USERNAME", "admin")
    password = os.environ.get("PIPEMAN_ADMIN_PASSWORD", "PasswordPassword")
    display = os.environ.get("PIPEMAN_ADMIN_DISPLAY", "Administrator")
    email = os.environ.get("PIPEMAN_ADMIN_EMAIL", "admin@example.com")
    admin_group = os.environ.get("PIPEMAN_ADMIN_GROUP", "superuser")
    try:
        duc.create_user_cli(username, email, display, password)
    except UserInputError as ex:
        pass
    try:
        duc.assign_to_group_cli(admin_group, username)
    except UserInputError as ex:
        pass
