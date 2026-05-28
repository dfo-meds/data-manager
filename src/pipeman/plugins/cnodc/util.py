import typing as t
import zirconium as zr

from pipeman.dataset.dataset import Dataset


def generate_canonical_urls(dataset: Dataset, format_: str | None = None, cfg: zr.ApplicationConfig = None) -> t.Iterable[dict]:
    replacements = {
        '{guid}': dataset.guid(),
    }
    templates: dict[str, list[str] | str] = cfg.get(("cnodc", "canonical_url_templates"), default={})
    if format_ is None:
        for f in templates.keys():
            yield from _build_canon_urls(templates[f], replacements, f)
    elif format_ in templates:
        yield from _build_canon_urls(templates[format_], replacements, format_)

def _build_canon_urls(template_strings: list[str] | str, replacements: dict, format_: str) -> t.Iterable[dict]:
    if isinstance(template_strings, str):
        template_strings = [template_strings]

    for template_str in template_strings:
        for original, replacement in replacements.items():
            template_str = template_str.replace(original, replacement)
        # looks like a resource
        # should we add more options in the configuration here?
        yield {
            'url': {
                'und':  template_str
            },
            'protocol': 'https' if template_str.startswith('https://') else 'http',
            'function': 'completeMetadata',
            'name': {
                'en': f'Metadata [{format_}]',
                'fr': f'Métadonnées [{format_}]'
            },
            'goc_content_type': 'support_doc',
            'goc_formats': ['HTML'],
            'goc_languages': ['ENG', 'FRA']
        }




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
