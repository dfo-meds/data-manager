"""Command line tools related to authentication"""
import click
from pipeman.util import UserInputError


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
