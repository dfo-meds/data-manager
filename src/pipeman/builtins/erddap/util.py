

def preprocess_dataset(dataset, **kwargs):
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
            if var['role']['short_name'] == 'profile_id' or var['role']['short_name'] == 'profile_extra':
                cdm_profile_vars.append(var['destination_name'])
            if var['role']['short_name'] == 'timeseries_id' or var['role']['short_name'] == 'timeseries_extra':
                cdm_timeseries_vars.append(var['destination_name'])
            if var['role']['short_name'] == 'trajectory_id' or var['role']['short_name'] == 'trajectory_extra':
                cdm_trajectory_vars.append(var['destination_name'])
    #keywords = [x for x in dataset.keywords()]
    #keywords.sort()
    keywords = []
    return {
        "subset_vars": ",".join(subset_vars),
        "basic_keywords": ",".join(keywords),
        "altitude_proxy": altitude_proxy,
        "cdm_profile_vars": ",".join(cdm_profile_vars),
        "cdm_trajectory_vars": ",".join(cdm_trajectory_vars),
        "cdm_timeseries_vars": ",".join(cdm_timeseries_vars),
    }
