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


def time_precision_input(config: dict, attributes: dict, fc, field):
    target = config["mapping"]
    if target in attributes:
        field.set_from_raw(_map_netcdf_time_precision_to_erddap(attributes.pop(target)))


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
        if var['cf_role']:
            if var['cf_role']['short_name'] == 'profile_id':
                cdm_profile_vars.append(var['destination_name'])
            if var['cf_role']['short_name'] == 'timeseries_id':
                cdm_timeseries_vars.append(var['destination_name'])
            if var['cf_role']['short_name'] == 'trajectory_id':
                cdm_trajectory_vars.append(var['destination_name'])
        if var['erddap_role']:
            if var['erddap_role']['short_name'] == 'profile_extra':
                cdm_profile_vars.append(var['destination_name'])
            if var['erddap_role']['short_name'] == 'timeseries_extra':
                cdm_timeseries_vars.append(var['destination_name'])
            if var['erddap_role']['short_name'] == 'trajectory_extra':
                cdm_trajectory_vars.append(var['destination_name'])
    vars.update({
    })
    vars["global_attributes"].update({
        "cdm_profile_vars": ",".join(cdm_profile_vars),
        "cdm_trajectory_vars": ",".join(cdm_trajectory_vars),
        "cdm_timeseries_vars": ",".join(cdm_timeseries_vars),
        "subsetVariables": ",".join(subset_vars),
        "cdm_altitude_proxy": altitude_proxy,
        # info_link to infoUrl?
        # spatial_representation_type?
        
    })
    return vars
