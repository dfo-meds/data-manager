from .workflow import WorkflowRegistry
from .controller import WorkflowController
from .steps import ItemResult
from autoinject import injector
import asyncio
from pipeman.util.cron import CronDaemon


def init(system):
    system.on_cron_start(_setup_cron_jobs)
    system.on_cleanup(_wc_cleanup)
    system.on_cleanup(_wc_batch_process)


def _setup_cron_jobs(cron: CronDaemon):
    from pipeman.workflow.controller import  WorkflowCronThread
    cron.register_periodic_job("workflow_batch_processing", _wc_batch_process, minutes=5)
    cron.register_periodic_job("workflow_cleanup", _wc_cleanup, hours=24, off_peak_only=True)
    cron.register_cron_thread(WorkflowCronThread)


@injector.inject
def _wc_batch_process(st = None, wc: WorkflowController = None):
    asyncio.run(wc.async_batch_process_items(st))


@injector.inject
def _wc_cleanup(st = None, wc: WorkflowController = None):
    wc.cleanup_old_items(st)
