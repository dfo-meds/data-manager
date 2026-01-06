from pipeman.vocab import VocabularyTermController
import logging
from pipeman.dataset.dataset import Dataset


def preprocess_metadata_all(dataset: Dataset, **kwargs):
    erddap_ds_id = dataset["erddap_dataset_id"]
    erddap_data_type = dataset['erddap_dataset_type']
    f = dataset.get_field('erddap_servers')
    servers = dataset['erddap_servers']
    if not (erddap_ds_id and erddap_data_type and servers):
        return
    dtype_dir = 'tabledap'
    dtype_format = 'TableDAP'
    if erddap_data_type['short_name'].startswith('EDDGrid'):
        dtype_dir = 'griddap'
        dtype_format = 'GridDAP'
    erddap_distribution_servers = []
    for server in servers:
        base_url = server['base_url']
        if not base_url:
            continue
        erddap_distribution_servers.append({
            'responsibles': server['responsibles'],
            'links': [
                {
                    'url': _assemble_erddap_link(base_url, dtype_dir, erddap_ds_id),
                    'protocol': {
                        'short_name': f'ERDDAP:{dtype_dir}'
                    },
                    'function': {
                        'short_name': 'download'
                    },
                    'name': {
                        'en': 'ERDDAP Web Site',
                        'fr': 'Site web ERDDAP',
                    },
                    'goc_content_type': {
                        'short_name': 'dataset',
                        'display': {
                            'en': 'Dataset',
                            'fr': 'Données'
                        }
                    },
                    'goc_formats': [{
                        # 'short_name': f'ERDDAP {dtype_format} Dataset'
                        # TODO: have to get the new short_name approved first
                        'short_name': 'HTML'
                    }],
                    'goc_languages': ['eng'],
                },
                {
                    'url': _assemble_erddap_link(base_url, dtype_dir, erddap_ds_id, 'fr'),
                    'protocol': {
                        'short_name': f'ERDDAP:{dtype_dir}'
                    },
                    'function': {
                        'short_name': 'download'
                    },
                    'name': {
                        'en': 'ERDDAP Web Site (French)',
                        'fr': 'Site web ERDDAP (français)',
                    },
                    'goc_content_type': {
                        'short_name': 'dataset',
                        'display': {
                            'en': 'Dataset',
                            'fr': 'Données'
                        }
                    },
                    'goc_formats': [{
                        # 'short_name': f'ERDDAP {dtype_format} Dataset'
                        # TODO: have to get the new short_name approved first
                        'short_name': 'HTML'
                    }],
                    'goc_languages': ['fra'],
                }
            ]
        })
    if 'iso19115_custom_distribution_channels' in kwargs:
        kwargs['iso19115_custom_distribution_channels'].extend(erddap_distribution_servers)
    else:
        return {
            'iso19115_custom_distribution_channels': erddap_distribution_servers
        }


def _assemble_erddap_link(erddap_base, dtype_dir, dataset_id, lang='en'):
    if lang != 'en':
        lang = f"{lang}/"
    else:
        lang = ""
    if not erddap_base[-1] == '/':
        return f"{erddap_base}/{lang}{dtype_dir}/{dataset_id}".strip()
    else:
        return f"{erddap_base}{lang}{dtype_dir}/{dataset_id}".strip()


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
    if tp in ('month', 'day', 'hour', 'minute', 'second', 'tenth_second', 'hundredth_second', 'millisecond'):
        return tp
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
    if cdm_profile_vars:
        vars['global_attributes']['cdm_profile_variables'] = ','.join(cdm_profile_vars)
    if cdm_trajectory_vars:
        vars['global_attributes']['cdm_trajectory_variables'] = ','.join(cdm_trajectory_vars)
    if cdm_timeseries_vars:
        vars['global_attributes']['cdm_timeseries_variables'] = ','.join(cdm_timeseries_vars)
    if subset_vars:
        vars['global_attributes']['subsetVariables'] = ','.join(subset_vars)
    if altitude_proxy:
        vars['global_attributes']['cdm_altitude_proxy'] = altitude_proxy
    if dataset['info_link'] and dataset['info_link']['url']:
        vars['global_attributes']['infoUrl'] = dataset['info_link']['url']
    return vars
