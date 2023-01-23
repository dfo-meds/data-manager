import click
import getpass
from autoinject import injector
from .controller import DatabaseUserController
from pipeman.util import UserInputError
from pipeman.util.cli import no_error_wrapper


@click.group
def user():
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
def create(username, email, display="", password=None, password_entry="", no_error=False, duc: DatabaseUserController = None):
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
@click.option("--no-error", default=False, is_flag=True, type=bool)
@click.option("--password-entry", default="argument")
@click.option("--password", default=None)
@click.argument("username")
@injector.inject
def set_password(username, password=None, password_entry="", no_error=False, duc: DatabaseUserController = None):
    """Create a user account."""
    no_error_wrapper(
        no_error,
        duc.set_password_cli,
        username,
        _get_password(password_entry, password)
    )


@user.command
@click.argument("username")
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
@injector.inject
def disable_api_access(username, no_error=False, duc: DatabaseUserController = None):
    no_error_wrapper(
        no_error,
        duc.set_api_access,
        username,
        False
    )


@user.group
def group():
    pass


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
