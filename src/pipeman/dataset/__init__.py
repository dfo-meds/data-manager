from .dataset import MetadataRegistry
from .controller import DatasetController
from autoinject import injector as _injector


@_injector.inject
def dataset_gate_step_access(item_config: dict, ctx: dict, mode: str, dc: DatasetController = None):
    if 'dataset_id' not in ctx:
        return False
    ds = dc.load_dataset(ctx['dataset_id'])
    if mode == 'view':
        return dc.has_access(ds, 'view')
    elif mode == 'decide':
        return dc.has_access(ds, 'decide')
    else:
        return False