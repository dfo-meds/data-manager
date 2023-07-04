from pipeman.entity.entity import ValidationResult, combine_object_path
import yaml

import logging

from pipeman.dataset.dataset import Dataset
from pipeman.entity import FieldContainer, EntityController
from pipeman.entity.fields import Field
from pipeman.i18n import MultiLanguageString
from pipeman.util import load_object




def load_eovs():
    eov_url = "https://raw.githubusercontent.com/cioos-siooc/metadata-entry-form/main/src/eovs.json"


def cioos_dataset_validation(ds, object_path, profile, memo):
    errors = []
    if ds.data("metadata_owner"):
        owner_path = combine_object_path(object_path, [ds.field_label("metadata_owner")])
        errors.extend(_verify_cioos_contact(ds.data("metadata_owner"), owner_path, profile, memo))
    return errors


def _verify_cioos_contact(contact, contact_path, profile, memo):
    errors = []
    if not contact.data("email"):
        errors.append(ValidationResult(
            "cioos.validation.metadata_owner_no_email",
            combine_object_path(contact_path, [contact.field_label("email")]),
            "error",
            "CIOOS-01",
            profile
        ))
    if not contact.data("id_code"):
        # Must have a name or identifier
        if not (contact.data("organization_name") or contact.data("individual_name")):
            errors.append(ValidationResult(
                "cioos.validation.metadata_owner_no_id_code_or_name",
                combine_object_path(contact_path, [contact.field_label("id_code")]),
                "error",
                "CIOOS-02",
                profile
            ))
        else:
            errors.append(ValidationResult(
                "cioos.validation.metadata_owner_no_id_code",
                combine_object_path(contact_path, [contact.field_label("id_code")]),
                "warning",
                "CIOOS-03",
                profile
            ))
    else:
        ident = contact.data("id_system")
        ident_path = combine_object_path(contact_path, [contact.field_label("id_system")])
        if not ident:
            errors.append(ValidationResult(
                "cioos.validation.metadata_owner_no_id_system",
                ident_path,
                "error",
                "CIOOS-04",
                profile
            ))
        elif not ident.data("code_space"):
                errors.append(ValidationResult(
                    "cioos.validation.metadata_owner_no_id_code_space",
                    combine_object_path(ident_path, [ident.label(), ident.field_label("code_space")]),
                    "error",
                    "CIOOS-05",
                    profile
                ))
        else:
            is_org = bool(contact.data("organization_name")) or bool(contact.data("logo"))
            if is_org and not ident.data("code_space") == "https://ror.org/":
                errors.append(ValidationResult(
                    "cioos.validation.metadata_owner_org_no_ror",
                    combine_object_path(ident_path, [ident.label(), ident.field_label("code_space")]),
                    "error",
                    "CIOOS-06",
                    profile
                ))
            elif (not is_org) and not ident.data("code_space") == "https://orcid.org/":
                errors.append(ValidationResult(
                    "cioos.validation.metadata_owner_ind_no_orcid",
                    combine_object_path(ident_path, [ident.label(), ident.field_label("code_space")]),
                    "error",
                    "CIOOS-07",
                    profile
                ))
    return errors


def preprocess_yaml_format(dataset: Dataset, **kwargs):
    content = {
        'naming_authority': dataset.naming_authority(),
        'identifier': dataset.guid(),
        'charset': 'utf8',
        'hierarchylevel': 'dataset',
        'datestamp': dataset.metadata_modified_date().isoformat(),
        'language': 'en',
        'dataseturi': f"{dataset.naming_authority()}/{dataset.guid()}",
        'identification': {}
    }

    dlocale = dataset.data('default_locale')
    if dlocale:
        if dlocale['a2_language']:
            content['language'] = dlocale['a2_language']
            if dlocale['country']:
                content['language'] += f';{dlocale["country"]}'
    olocales = dataset.data('other_locales')
    if olocales:
        content['language_alternate'] = [x['a2_language'] for x in olocales]
    dslocale = dataset.data('dataset_locale')
    if dslocale:
        if dslocale['a2_language']:
            content['identification']['language'] = dslocale['a2_language']
            if dslocale['country']:
               content['identification']['language'] += f";{dslocale['country']}"
        if dslocale['encoding']:
            content['identification']['charset'] = dslocale['encoding']['short_name']

    keywords = {}
    for x in dataset.keywords():
        xg = x.thesaurus_group()
        if xg not in keywords:
            keywords[xg] = {'und': set()}
            for x in content['language_alternate']:
                keywords[xg][x] = set()
        if not x.use_value_only():
            for lang in x.translations:
                if lang in keywords[xg]:
                    keywords[xg][lang].add(x.translations[x][lang])
        if x.mode in ('both', 'value'):
            keywords[xg]['und'].add(x.machine_key)
    content['identification']['keywords'] = keywords

    if dataset.data("bbox_west") is not None:
        content['spatial']['bbox'] = [
            dataset.data("bbox_west"),
            dataset.data("bbox_south"),
            dataset.data("bbox_east"),
            dataset.data("bbox_north"),
        ]

    if dataset.data("vertical_min") is not None:
        content['spatial']['vertical'] = [
            dataset.data("vertical_min"),
            dataset.data("vertical_max"),
        ]

    content.update(_extract_mcf_attributes(dataset))
    return {
        'yaml_content': yaml.dump(content)
    }


def _extract_mcf_attributes(fc: FieldContainer):
    attrs = {}
    for fn in fc.ordered_field_names():
        field = fc.get_field(fn)
        if field.is_empty():
            continue
        config = field.config("iso_yaml", default=None)
        if not config:
            continue
        processor = config['processor'] if 'processor' in config and config['processor'] else field.config('data_type')
        _process_field_value(processor, attrs, config['mapping'], field, config, fc)
    return attrs


def _process_field_value(processor: str, *args):
    if processor in ('text', 'multitext', 'email', 'url', 'telephone'):
        _text_processor(*args)
    elif processor in ('date', 'datetime'):
        _datetime_processor(*args)
    elif processor in ('decimal', 'integer', 'float'):
        _numeric_processor(*args)
    else:
        try:
            obj = load_object(processor)
            obj(*args)
        except (AttributeError, ModuleNotFoundError) as ex:
            logging.getLogger("pipeman.mcf").exception("MCF processor {processor} not found")


def _text_processor(attrs: dict, target_map: list, field: Field, config: dict, fc: FieldContainer):
    _set_deep_value(attrs, target_map, field.data())


def _datetime_processor(attrs: dict, target_map: list, field: Field, config: dict, fc: FieldContainer):
    if field.is_repeatable():
        _set_deep_value(attrs, target_map, [x.isoformat() for x in field.data()])
    else:
        _set_deep_value(attrs, target_map, field.data().isoformat())


def _numeric_processor(attrs: dict, target_map: list, field: Field, config: dict, fc: FieldContainer):
    _set_deep_value(attrs, target_map, field.data())


def _vocabulary_processor(attrs: dict, target_map: list, field: Field, config: dict, fc: FieldContainer):
    if field.is_repeatable():
        _set_deep_value(attrs, target_map, [x['short_name'] for x in field.data()])
    else:
        _set_deep_value(attrs, target_map, field.data()['short_name'])


def _set_deep_value(attrs: dict, target_map: list, value, cleanup: bool = True):
    t = attrs
    for x in target_map[:-1]:
        if x not in t:
            t[x] = {}
        t = t[x]
    t[target_map[-1]] = _cleanup_text(value) if cleanup else value


def _cleanup_text(txt):
    if isinstance(txt, (list, tuple)):
        return [_cleanup_text(t) for t in txt]
    if isinstance(txt, MultiLanguageString):
        return {
            x: txt.language_map[x]
            for x in txt.language_map
            if x[0] != '_' and txt.language_map[x]}
    return txt

