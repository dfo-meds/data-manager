import click
import getpass
from pipeman.util import UserInputError


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
        raise UserInputError("Random password not yet supported")
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
def create(username, email, display="", password=None, password_entry="", no_error=False):
    """Create a user account."""
    from .util import create_user
    if display == "":
        display = username
    try:
        create_user(username, display, email, _get_password(password_entry, password))
    except UserInputError as ex:
        if no_error:
            print(str(ex))
        else:
            raise ex


@user.command
@click.option("--no-error", default=False, is_flag=True, type=bool)
@click.argument("username")
@click.argument("group_name")
def assign_to(username, group_name, no_error=False):
    from .util import assign_to_group
    try:
        assign_to_group(group_name, username)
    except UserInputError as ex:
        if no_error:
            print(str(ex))
        else:
            raise ex


@user.command
@click.option("--no-error", default=False, is_flag=True, type=bool)
@click.argument("username")
@click.argument("group_name")
def remove_from(username, group_name, no_error=False):
    from .util import remove_from_group
    try:
        remove_from_group(group_name, username)
    except UserInputError as ex:
        if no_error:
            print(str(ex))
        else:
            raise ex
