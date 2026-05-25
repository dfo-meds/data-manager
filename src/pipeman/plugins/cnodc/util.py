from pipeman.dataset.dataset import Dataset


def preprocess_metadata_all(dataset: Dataset, **kwargs):
    req = dataset.data('via_meds_request_form')
    servers = []
    if req:
        servers.append({
            'responsibles': [
                {
                    'role': {'short_name': 'distributor'},
                    'contact': {
                        'organization_name': {
                            'en': 'Marine Environmental Data Section',
                            'fr': 'Section des données sur le milieu marin'
                        }
                    }
                }
            ],
            'links': [
                {
                    'url': 'https://meds-sdmm.dfo-mpo.gc.ca/isdm-gdsi/request-commande/form-eng.asp',
                    'protocol': {'short_name': 'http'},
                    'function': {'short_name': 'service'},
                    'name': {
                        'en': 'MEDS Data Request Form',
                        'fr': 'Formulaire de commande de SDMM'
                    }
                }
            ]
        })
        if 'iso19115_custom_distribution_channels' in kwargs:
            kwargs['iso19115_custom_distribution_channels'].extend(servers)
        else:
            return {
                'iso19115_custom_distribution_channels': servers
            }
