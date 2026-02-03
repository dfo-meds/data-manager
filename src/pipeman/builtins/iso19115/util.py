from pipeman.db import Database, orm
from pipeman.entity import Entity
from pipeman.entity.entity import ValidationResult, combine_object_path
from pipeman.entity.keywords import KeywordGroup
import functools

from autoinject import injector

def validate_use_constraint(uc, object_path, profile, memo):
    errors = []
    if uc['classification']:
        if uc['access_constraints']:
            errors.append(("pipeman.iso19115.security_constraint_has_access", "ISO19115-001"))
        if uc['use_constraints']:
            errors.append(("pipeman.iso19115.security_constraint_has_use", "ISO19115-002"))
        if uc['other_constraints']:
            errors.append(("pipeman.iso19115.security_constraint_has_other", "ISO19115-003"))
    elif uc['user_notes'] or uc['classification_system'] or uc['handling_description']:
        errors.append(("pipeman.iso19115.security_constraint_missing_classification", "ISO19115-004"))
    else:
        if uc['use_constraints'] and any(x.short_name() == 'otherRestrictions' for x in uc['use_constraints']) and not uc['other_constraints']:
            errors.append(("pipeman.iso19115.legal_constraint_missing_other", "ISO19115-005"))
        elif uc['access_constraints'] and any(x.short_name() == 'otherRestrictions' for x in uc['access_constraints'])  and not uc['other_constraints']:
            errors.append(("pipeman.iso19115.legal_constraint_missing_other", "ISO19115-006"))
    return errors


def validate_time_res(tr, object_path, profile, memo):
    if not (tr['years'] or tr['months'] or tr['days'] or tr['hours'] or tr['minutes'] or tr['seconds']):
        return [("pipeman.iso19115.time_res_incomplete", "ISO19115-020")]
    return []


def validate_spatial_res(sr, object_path, profile, memo):
    errors = []
    if not (sr['scale'] or sr['distance'] or sr['vertical'] or sr['angular'] or sr['level_of_detail']):
        errors.append(("pipeman.iso19115.spatial_res_incomplete", "ISO19115-060"))
    if sr["distance"] and not sr["distance_units"]:
        errors.append(("pipeman.iso19115.spatial_res_missing_distance_units", "ISO19115-061"))
    if sr["vertical"] and not sr["vertical_units"]:
        errors.append(("pipeman.iso19115.spatial_res_missing_vertical_units", "ISO19115-062"))
    if sr["angular"] and not sr["angular_units"]:
        errors.append(("pipeman.iso19115.spatial_res_missing_angular_units", "ISO19115-063"))
    return errors


def validate_citation(cit, object_path, profile, memo):
    errors = []
    if (cit['id_system'] or cit['id_description']) and not cit['id_code']:
        errors.append(("pipeman.iso19115.contact_missing_id_code", "ISO19115-080", "warning"))
    return errors


def validate_contact(con, object_path, profile, memo):
    errors = []
    if not (con['individual_name'] or con['organization_name'] or con['position_name'] or con['logo']):
        errors.append(("pipeman.iso19115.contact_name_required", "ISO19115-030"))
    if con['organization_name'] or con['logo']:
        if con['individual_name']:
            errors.append(("pipeman.iso19115.org_has_individual_name", "ISO19115-031"))
        if con['position_name']:
            errors.append(("pipeman.iso19115.org_has_position_name", "ISO19115-032"))
        if any(x['organization_name'] or x['logo'] for x in con['individuals']):
            errors.append(("pipeman.iso19115.org_has_orgs", "ISO19115-033"))
    else:
        if con['individuals']:
            errors.append(("pipeman.iso19115.individual_has_individuals", "ISO19115-034"))
    if (con['id_system'] or con['id_description']) and not con['id_code']:
        errors.append(("pipeman.iso19115.contact_missing_id_code", "ISO19115-035", "warning"))
    return errors


def validate_releasability(rel, object_path, profile, memo):
    errors = []
    if not (rel['addressees'] or rel['statement']):
        errors.append(("pipeman.iso19115.releasability_requires_addressee_or_statement", "ISO19115-050"))
    return errors


def validate_dataset(ds, object_path, profile, memo):
    errors = []
    if (ds['processing_system'] or ds['processing_desc']) and not ds['processing_code']:
        errors.append(ValidationResult(
            "pipeman.iso19115.missing_processing_code",
            combine_object_path(object_path, ds.field_label("processing_code")),
            "warning",
            "ISO19115-070",
            profile
        ))
    if (ds['dataset_id_desc'] or ds['dataset_id_system']) and not ds['dataset_id_code']:
        errors.append(ValidationResult(
            "pipeman.iso19115.missing_id_code",
            combine_object_path(object_path, ds.field_label("dataset_id_code")),
            "warning",
            "ISO19115-071",
            profile
        ))
    return errors


def separate_keywords(keywords):
    groups = {}
    for keyword in keywords:
        group = keyword.thesaurus_group()
        if group not in groups:
            groups[group] = KeywordGroup(keyword.thesaurus)
        groups[group].append(keyword)
    return groups


def _has_other_languages(language_dict, default_locale, supported_locales):
    for key in language_dict:
        if key == "und" or key == default_locale:
            continue
        if key not in supported_locales:
            continue
        return True
    return False


def _has_type_been_rendered(ref_dict: dict, type_name: str, unique_id):
    if not unique_id:
        return False
    if type_name not in ref_dict:
        ref_dict[type_name] = set()
    if unique_id not in ref_dict[type_name]:
        ref_dict[type_name].add(unique_id)
        return False
    return True

def _clean_xml_id(type_name, xml_id, db_id):
    new_xml_id = ""
    if xml_id:
        for ltr in xml_id:
            if ltr in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-":
                new_xml_id += ltr
    if not new_xml_id:
        new_xml_id = "_" + str(db_id)
    return f"{type_name}_{new_xml_id}"

@injector.inject
def get_platform_instruments(platform, db: Database = None):
    with db as session:
        for instrument in session.query(orm.Entity).filter_by(entity_type="instrument"):
            if instrument['mounted_on'].db_id == platform.db_id:
                yield instrument

def preprocess_metadata(dataset, **kwargs):
    locale_mapping = {}
    def_loc = dataset.data("default_locale")
    default_locale = def_loc['a2_language'] if def_loc else "en"
    locale_mapping[default_locale] = def_loc['language'] if def_loc else "eng"
    olocales = dataset.data("other_locales") or []
    supported = []
    for other_loc in olocales:
        locale_mapping[other_loc['a2_language']] = other_loc['language']
        supported.append(other_loc['a2_language'])
    dataset_maintenance = []
    metadata_maintenance = []
    for maintenance in dataset.data("iso_maintenance") or []:
        if maintenance['scope']['short_name'] == "dataset":
            dataset_maintenance.append(maintenance)
        elif maintenance['scope']['short_name'] == "metadata":
            metadata_maintenance.append(maintenance)
    refs = {}
    return {
        "responsibilities": [
            {
                "role": {"short_name": "owner"},
                "contact": dataset['metadata_owner']
            }
        ],
        "dates": [
            {
                "type": {"short_name": "created"},
                "date": dataset.created_date()
            },
            {
                "type": {"short_name": "revision"},
                "date": dataset.metadata_modified_date()
            },
        ],
        "default_locale": default_locale,
        "locale_mapping": locale_mapping,
        "dataset_citation": {
            "title": dataset.data("title"),
            "publication_date": dataset["publication_date"],
            "revision_date": dataset["revision_date"],
            "creation_date": dataset["creation_date"],
            "id_code": dataset["dataset_id_code"],
            "id_system": dataset["dataset_id_system"],
            "id_description": dataset["dataset_id_desc"],
            "responsibles": dataset["responsibles"],
            'resource': dataset['info_link']
        },
        "dataset_maintenance": dataset_maintenance,
        "metadata_maintenance": metadata_maintenance,
        "grouped_keywords": separate_keywords(dataset.keywords()),
        "check_alt_langs": functools.partial(_has_other_languages, supported_locales=supported),
        '_refs': refs,
        'check_platform': functools.partial(_has_type_been_rendered, refs, 'platform'),
        'check_instrument': functools.partial(_has_type_been_rendered, refs, 'instrument'),
        'check_mission': functools.partial(_has_type_been_rendered, refs, 'mission'),
        'clean_id': _clean_xml_id,
        'get_platform_instruments': get_platform_instruments
    }
