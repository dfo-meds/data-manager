import click
from pipeman.util import UserInputError


@click.group
def group():
    pass


@group.command
@click.option("--no-error", default=False, is_flag=True, type=bool)
@click.argument("group_name")
def create(group_name, no_error=False):
    """Create a user account."""
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
def grant(group_name, perm_name, no_error=False):
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
def revoke(group_name, perm_name, no_error=False):
    from .util import revoke_permission
    try:
        revoke_permission(group_name, perm_name)
    except UserInputError as ex:
        if no_error:
            print(str(ex))
        else:
            raise ex
