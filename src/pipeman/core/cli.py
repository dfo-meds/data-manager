import click


@click.group
def org():
    pass


@org.command
@click.argument("org_name")
def create(org_name):
    from .util import create_organization
    create_organization(org_name)
