from pipeman.vocab import VocabularyTermController
import logging

TIME_PRECISION_MAP = {
    "month": "1970-01",
    "day": "1970-01-01",
    "hour": "1970-01-01T00Z",
    "minute": "1970-01-01T00:00Z",
    "second": "1970-01-01T00:00:00Z",
    "tenth_second": "1970-01-01T00:00:00.0Z",
    "hundredth_second": "1970-01-01T00:00:00.00Z",
    "millisecond": "1970-01-01T00:00:00.000Z",
}


def time_precision_output(attrs: dict, target_name: str, field, config: dict, fc):
    vocab_item = field.data()
    if vocab_item:
        tp_name = vocab_item['short_name']
        if tp_name in TIME_PRECISION_MAP:
            attrs[target_name] = TIME_PRECISION_MAP[tp_name]
        else:
            logging.getLogger("pipeman.erddap").error(f"Time precision value {tp_name} not recognized")


def set_metadata_from_netcdf(dataset, file_type: str, metadata: dict, vtc: VocabularyTermController = None):
    md = metadata['global']
    if 'standard_name_vocab' in md:
        dataset.get_field('standard_name_vocab').value = md['standard_name_vocab']
    if 'summary' in md:
        dataset.get_field('abstract').value = _map_netcdf_text_to_multilingual(md, 'summary', 'sommaire')
    if 'title' in md:
        dataset.get_field('title').value = _map_netcdf_text_to_multilingual(md, 'title', 'titre')
    if 'acknowledgement' in md:
        dataset.get_field('credit').value = _map_netcdf_text_to_multilingual(md, 'acknowledgement', 'reconnaissance')
    if 'processsing_code' in md:
        dataset.get_field('processing_code').value = md['processing_code']
    if 'project' in md:
        dataset.get_field('project').value = md['project']
    # Publisher name, email, type, url
    # Subset vars
    # Keywords
    # CDM altitude proxy
    # CDM profile, trajectory, timeseries variables
    variables = dataset.get_field("variables")
    current_variables = {}
    for c in variables.component_list():
        name = c["source_name"]
        if not name:
            name = c["short_name"]
        current_variables[name] = c
    for sname in metadata["variables"]:
        nvar = metadata["variables"][sname]
        if sname not in current_variables:
            # create a new one
            pass
        else:
            var = current_variables[sname]
            var.get_field("source_name").value = sname
            var.get_field("short_name").value = sname
            if "_data_type" in nvar:
                var.get_field("source_data_type").value = vtc.get_term_id(
                    'erddap_data_types',
                    _map_netcdf_datatype_to_erddap(nvar["_data_type"])
                )
            if "ioos_category" in nvar:
                var.get_field("ioos_category").value = vtc.get_term_id(
                    'ioos_categories',
                    nvar['ioos_category']
                )
            if 'units' in nvar:
                var.get_field('units').value = nvar['units']
            if '_Encoding' in nvar:
                var.get_field('encoding').value = vtc.get_term_id(
                    'erddap_encodings',
                    nvar['_Encoding']
                )
            if 'standard_name' in nvar:
                var.get_field('standard_name').value = nvar['standard_name']
            if 'missing_value' in nvar:
                var.get_field('fill_value').value = nvar['missing_value']
            elif '_FillValue' in nvar:
                var.get_field('fill_value').value = nvar['_FillValue']
            if 'scale_factor' in nvar:
                var.get_field('scale_factor').value = nvar['scale_factor']
            if 'add_offset' in nvar:
                var.get_field('add_offset').value = nvar['add_offset']
            if 'time_precision' in nvar:
                var.get_field('time_precision').value = vtc.get_term_id(
                    'erddap_time_precisions',
                    _map_netcdf_time_precision_to_erddap(nvar['time_precision'])
                )
            if 'time_zone' in nvar:
                var.get_field('time_zone').value = vtc.get_term_id(
                    'timezones',
                    nvar['time_zone']
                )
            if 'actual_min' in nvar:
                var.get_field('min_value').value = nvar['actual_min']
            if 'actual_max' in nvar:
                var.get_field('max_value').value = nvar['actual_max']
            if 'valid_min' in nvar:
                var.get_field('valid_min').value = nvar['valid_min']
            if 'valid_max' in nvar:
                var.get_field('valid_max').value = nvar['valid_max']
            if 'cf_role' in nvar:
                var.get_field('role').value = vtc.get_term_id(
                    'erddap_roles',
                    nvar['cf_role']
                )
            if "long_name" in nvar:
                var.get_field("long_name").value = _map_netcdf_text_to_multilingual(nvar, 'long_name', 'nom_long')


def _map_netcdf_time_precision_to_erddap(tp):
    if tp.count('-') == 0:
        raise ValueError('Year precision not allowed')
    elif tp.count('-') == 1:
        return 'month'
    elif tp.count('T') == 0:
        return 'day'
    elif tp.count(':') == 0:
        return 'hour'
    elif tp.count(':') == 1:
        return 'minute'
    elif tp.count('.') == 0:
        return 'second'
    else:
        ending = tp[tp.find(".")+1:]
        if ending[-1] == "Z":
            ending = ending[:-1]
        if len(ending) == 0:
            return 'second'
        if len(ending) == 1:
            return 'tenth_second'
        elif len(ending) == 2:
            return 'hundredth_second'
        else:
            return 'millisecond'


def _map_netcdf_text_to_multilingual(d: dict, en_key: str, fr_key: str):
    if "|" in val:
        pieces = val.split("|", maxsplit=1)
        return {"en": pieces[0], "fr": pieces[1]}
    else:
        return {"und": val}


def _map_netcdf_datatype_to_erddap(netcdf_dt: str) -> str:
    if netcdf_dt == 'str':
        return 'String'
    if netcdf_dt in ('S1', 'c'):
        return 'char'
    if netcdf_dt in ('i2', 'h', 's'):
        return 'short'
    if netcdf_dt in ('i1', 'b', 'B'):
        return 'byte'
    if netcdf_dt in ('i', 'l', 'i4'):
        return 'int'
    if netcdf_dt in ('f', 'f4'):
        return 'float'
    if netcdf_dt in ('d', 'f8'):
        return 'double'
    if netcdf_dt == 'i8':
        return 'long'
    if netcdf_dt == 'u8':
        return 'ulong'
    if netcdf_dt == 'u4':
        return 'uint'
    if netcdf_dt == 'u2':
        return 'ushort'
    if netcdf_dt == 'u1':
        return 'ubyte'
    raise ValueError(f'Unrecognized NetCDF datatype: {netcdf_dt}')


def preprocess_dataset(dataset, **kwargs):
    from pipeman.builtins.netcdf.util import _preprocess_for_both
    vars = _preprocess_for_both(dataset, **kwargs)
    subset_vars = []
    altitude_proxy = None
    cdm_profile_vars = []
    cdm_timeseries_vars = []
    cdm_trajectory_vars = []
    for var in dataset['variables']:
        if var['allow_subsets']:
            subset_vars.append(var['destination_name'])
        if var['altitude_proxy']:
            altitude_proxy = var['destination_name']
        if var['role']:
            # TODO: fix the fact we removed the _extra names
            if var['role']['short_name'] == 'profile_id' or var['role']['short_name'] == 'profile_extra':
                cdm_profile_vars.append(var['destination_name'])
            if var['role']['short_name'] == 'timeseries_id' or var['role']['short_name'] == 'timeseries_extra':
                cdm_timeseries_vars.append(var['destination_name'])
            if var['role']['short_name'] == 'trajectory_id' or var['role']['short_name'] == 'trajectory_extra':
                cdm_trajectory_vars.append(var['destination_name'])
    vars.update({
        "subset_vars": ",".join(subset_vars),
        "altitude_proxy": altitude_proxy,
        "cdm_profile_vars": ",".join(cdm_profile_vars),
        "cdm_trajectory_vars": ",".join(cdm_trajectory_vars),
        "cdm_timeseries_vars": ",".join(cdm_timeseries_vars),
    })
    return vars
