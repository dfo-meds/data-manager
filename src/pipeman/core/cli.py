import click
from autoinject import injector
from pipeman.org import OrganizationController
from pipeman.workflow import WorkflowController
import asyncio


@click.group
def org():
    pass


@org.command
@click.argument("org_name")
@injector.inject
def create(org_name, org_controller: OrganizationController = None):
    org_controller.upsert_organization(org_name)


@click.group
def workflow():
    pass


@workflow.command
@injector.inject
def batch(wfc: WorkflowController):
    wfc.batch_process_items()


@workflow.command
@injector.inject
def async_batch(wfs: WorkflowController):
    asyncio.run(wfs.async_batch_process_items())
