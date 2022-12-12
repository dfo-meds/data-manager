import click
from autoinject import injector
from pipeman.org import OrganizationController


@click.group
def org():
    pass


@org.command
@click.argument("org_name")
@injector.inject
def create(org_name, org_controller: OrganizationController = None):
    org_controller.upsert_organization(org_name)
