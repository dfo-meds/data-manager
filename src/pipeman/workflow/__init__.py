from .workflow import WorkflowRegistry
from .controller import WorkflowController
from .steps import ItemResult
from autoinject import injector
import asyncio
from pipeman.core.util import CronDaemon


def init(system):
    system.on_cron_start(_setup_cron_jobs)
    system.on_cleanup(_wc_cleanup)
    system.on_cleanup(_wc_batch_process)


def _setup_cron_jobs(cron: CronDaemon):
    cron.register_periodic_job("workflow_batch_processing", _wc_batch_process, minutes=5)
    cron.register_periodic_job("workflow_cleanup", _wc_cleanup, hours=24, off_peak_only=True)


@injector.inject
def _wc_batch_process(wc: WorkflowController = None):
    wc.batch_process_items()
    asyncio.run(wc.async_batch_process_items())


@injector.inject
def _wc_cleanup(wc: WorkflowController = None):
    wc.cleanup_old_items()
