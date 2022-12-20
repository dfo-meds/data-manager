import universalio as uio
from .files import DataStoreRegistry
from pipeman.workflow import WorkflowController
from autoinject import injector
from pipeman.workflow import ItemResult


@injector.inject
async def split_send_files(action_config, item_context, dsr: DataStoreRegistry = None, wc: WorkflowController = None):
    remote_dir = uio.FileWrapper(dsr.data_store_path(item_context['data_store_name']))
    remote_file = remote_dir / item_context['filename']
    item_context['remote_path'] = str(remote_file)
    item_context['exists'] = await remote_file.exists_async()
    if item_context['exists'] and not dsr.allow_overwrite(item_context['data_store_name']):
        # todo raise error
        pass
    workflow = dsr.get_workflow_name(item_context['data_store_name'], item_context['exists'])
    wc.start_workflow("send_file", workflow, item_context, item_context['_id'])
    return ItemResult.SUCCESS


@injector.inject
async def upload_file(action_config, item_context, dsr: DataStoreRegistry = None):
    local_file = uio.FileWrapper(item_context['local_path'])
    remote_file = await local_file.copy_async(
        uio.FileWrapper(item_context['remote_path']),
        allow_overwrite=dsr.allow_overwrite(item_context['data_store_name'])
    )
    result = await remote_file.exists_async()
    if result and item_context['remove_on_completion']:
        await local_file.remove_async()
    return result
