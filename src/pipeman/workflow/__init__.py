from .workflow import WorkflowController, WorkflowRegistry, ItemResult
from autoinject import injector
import asyncio


def init(system):
    system.on_cleanup(_do_cleanup)


@injector.inject
def _do_cleanup(wc: WorkflowController = None):
    wc.batch_process_items()
    asyncio.run(wc.async_batch_process_items())
