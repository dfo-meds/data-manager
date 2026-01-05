"""Command line tools related to authentication"""
from pipeman.util import UserInputError
import click
import getpass
from autoinject import injector
from pipeman.auth.controller import DatabaseUserController
from pipeman.util.cli import no_error_wrapper
import typing as t


@click.group
def group():
    """Group management."""
    pass


@group.command
@click.option("--no-error", default=False, is_flag=True, type=bool)
@click.argument("group_name")
def create(group_name: str, no_error: bool = False):
    """Create a group."""
    from .util import create_group
    try:
        create_group(group_name)
    except UserInputError as ex:
        if no_error:
            print(str(ex))
        else:
            raise ex


@group.command
@click.option("--no-error", default=False, is_flag=True, type=bool)
@click.argument("group_name")
@click.argument("perm_name")
def grant(group_name: str, perm_name: str, no_error: bool = False):
    """Grant a permission to a group."""
    from .util import grant_permission
    try:
        grant_permission(group_name, perm_name)
    except UserInputError as ex:
        if no_error:
            print(str(ex))
        else:
            raise ex


@group.command
@click.option("--no-error", default=False, is_flag=True, type=bool)
@click.argument("group_name")
@click.argument("perm_name")
def revoke(group_name: str, perm_name: str, no_error: bool = False):
    """Revoke a permission from a group."""
    from .util import revoke_permission
    try:
        revoke_permission(group_name, perm_name)
    except UserInputError as ex:
        if no_error:
            print(str(ex))
        else:
            raise ex


@group.command
@click.option("--no-error", default=False, is_flag=True, type=bool)
@click.argument("group_name")
def clear_permissions(group_name: str, no_error: bool = False):
    """Revoke a permission from a group."""
    from .util import clear_permissions
    try:
        clear_permissions(group_name)
    except UserInputError as ex:
        if no_error:
            print(str(ex))
        else:
            raise ex


@click.group
def user():
    """User commands"""
    pass


def _get_password(password_entry: str, arg_password: str) -> str:
    """Retrieve a password either from the input, at random, or from the passed argument.

    Parameters
    ----------
    password_entry: str
        One of "random", "input" or "argument". If random, a random password is generated. If input, the password is
        requested using getpass.getpass(). Otherwise, the argument is used.
    arg_password: str
        The password from the option.
    Returns
    -------
    A password to use for the user.
    """
    pw = arg_password
    if password_entry == "random":  # noqa: S105
        pw = None
    elif password_entry == "input":  # noqa: S105
        pw_test = getpass.getpass("Password: ")
        pw_test2 = getpass.getpass("Retype Password: ")
        while not pw_test == pw_test2:
            print("Passwords do not match, please try again")
            pw_test = getpass.getpass("Password: ")
            pw_test2 = getpass.getpass("Retype Password: ")
        pw = pw_test
    return pw


@user.command
@click.option("--display", default="")
@click.option("--no-error", default=False, is_flag=True, type=bool)
@click.option("--password-entry", default="argument")
@click.option("--password", default=None)
@click.argument("username")
@click.argument("email")
@injector.inject
def create(username: str, email: str, display: str = "", password: t.Optional[str] = None, password_entry="", no_error=False, duc: DatabaseUserController = None):
    """Create a user account."""
    if display == "":
        display = username
    no_error_wrapper(
        no_error,
        duc.create_user_cli,
        username,
        email,
        display,
        _get_password(password_entry, password)
    )


@user.command
@click.argument("username")
@injector.inject
def unlock(username, duc: DatabaseUserController = None):
    """Unlock a user account."""
    duc.unlock_user_account(username)


@user.command
@click.option("--no-error", default=False, is_flag=True, type=bool)
@click.option("--password-entry", default="argument")
@click.option("--password", default=None)
@click.argument("username")
@injector.inject
def set_password(username, password=None, password_entry="", no_error=False, duc: DatabaseUserController = None):
    """Set the password for a user."""
    no_error_wrapper(
        no_error,
        duc.set_password_cli,
        username,
        _get_password(password_entry, password)
    )


@user.command
@click.argument("username")
@click.option("--no-error", default=False, is_flag=True, type=bool)
@injector.inject
def enable_api_access(username, no_error=False, duc: DatabaseUserController = None):
    no_error_wrapper(
        no_error,
        duc.set_api_access,
        username,
        True
    )


@user.command
@click.argument("username")
@click.option("--no-error", default=False, is_flag=True, type=bool)
@injector.inject
def disable_api_access(username, no_error=False, duc: DatabaseUserController = None):
    no_error_wrapper(
        no_error,
        duc.set_api_access,
        username,
        False
    )


@user.command
@click.argument("username")
@click.argument("display")
@click.argument("expiry_days")
@click.option("--no-error", default=False, is_flag=True, type=bool)
@injector.inject
def create_api_key(username, display, expiry_days, no_error=False, duc: DatabaseUserController = None):
    no_error_wrapper(
        no_error,
        duc.create_api_key,
        username,
        display,
        int(expiry_days)
    )


@user.command
@click.argument("username")
@click.argument("prefix")
@click.argument("expiry_days")
@click.argument("leave_old_active_days")
@click.option("--no-error", default=False, is_flag=True, type=bool)
@injector.inject
def rotate_api_key(username, prefix, expiry_days, leave_old_active_days, no_error=False, duc: DatabaseUserController = None):
    no_error_wrapper(
        no_error,
        duc.rotate_api_key,
        username,
        prefix,
        int(expiry_days),
        int(leave_old_active_days)
    )


@group.command
@click.option("--no-error", default=False, is_flag=True, type=bool)
@click.argument("username")
@click.argument("group_name")
@injector.inject
def assign(username, group_name, no_error=False, duc: DatabaseUserController = None):
    no_error_wrapper(
        no_error,
        duc.assign_to_group_cli,
        group_name,
        username
    )


@group.command
@click.option("--no-error", default=False, is_flag=True, type=bool)
@click.argument("username")
@click.argument("group_name")
@injector.inject
def remove(username, group_name, no_error=False, duc: DatabaseUserController = None):
    no_error_wrapper(
        no_error,
        duc.remove_from_group_cli,
        group_name,
        username
    )


@user.group
def org():
    pass


@org.command("assign")
@click.option("--no-error", default=False, is_flag=True, type=bool)
@click.argument("username")
@click.argument("org_name")
@injector.inject
def assign_org(username, org_name, no_error=False, duc: DatabaseUserController = None):
    no_error_wrapper(
        no_error,
        duc.assign_to_org_cli,
        org_name,
        username
    )


@org.command("remove")
@click.option("--no-error", default=False, is_flag=True, type=bool)
@click.argument("username")
@click.argument("org_name")
@injector.inject
def remove_org(username, org_name, no_error=False, duc: DatabaseUserController = None):
    no_error_wrapper(
        no_error,
        duc.remove_from_group_cli,
        org_name,
        username
    )
