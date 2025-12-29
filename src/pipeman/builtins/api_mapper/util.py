from pipeman.dataset.dataset import Dataset
from pipeman.entity.fields import Field
from pipeman.entity.entity import FieldContainer
from pipeman.i18n import TranslationManager
from autoinject import injector
import logging


@injector.inject
def set_metadata_from_api(dataset: Dataset, file_type: str, metadata: dict, tm: TranslationManager = None):
    for field_name in dataset.ordered_field_names():
        field = dataset.get_field(field_name)
        config = field.config("json_api", default=None)
        if config is None:
            continue
        api_name = field_name if 'mapping' not in config or not config['mapping'] else config['mapping']
        if api_name not in metadata:
            continue
        data_type = field.config("data_type", default=None)
        if data_type in ("text", "multitext", "decimal", "date", "datetime", "email", "float", "integer", "choice", "telephone", "time", "url", ):
            _handle_raw_from_api(field, metadata[api_name])
        # TODO: vocabulary (need to lookup) <-- gonna need this atl east
        # TODO: dataset reference (need to lookup?)
        # TODO: inline entity reference (need to build if it does not exist?) <-- at least for variables?
        # TODO: entity reference (need to lookup or make?)
        else:
            logging.getLogger("pipeman.api_mapper").warning(f"Value specified for metadata field [{field_name}] but no mapping for [{data_type}] available")

def _handle_raw_from_api(f: Field, api_value):
    f.set_from_raw(api_value)


