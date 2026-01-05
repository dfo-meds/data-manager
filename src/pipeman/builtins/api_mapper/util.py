import functools
import logging

from pipeman.entity.entity import FieldContainer



def set_metadata_from_api(fc: FieldContainer, metadata: dict, file_type: str, results: dict):
    for field_name in fc.ordered_field_names():
        field = fc.get_field(field_name)
        config = field.config("json_api", default=None)
        if config is None:
            continue
        api_name = field_name if 'mapping' not in config or not config['mapping'] else config['mapping']
        if api_name not in metadata:
            continue
        try:
            field.set_from_external(metadata[api_name], functools.partial(set_metadata_from_api, results=results, file_type=file_type))
        except Exception as ex:
            logging.getLogger("pipeman.api_mapper").warning(f"Error mapping API data value for [{field_name}]")
            logging.exception(ex)
