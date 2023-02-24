
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
        if uc['use_constraints'] and uc['use_constraints']['short_name'] == 'otherRestrictions' and not uc['other_constraints']:
            errors.append(("pipeman.iso19115.legal_constraint_missing_other", "ISO19115-005"))
        elif uc['access_constraints'] and uc['access_constraints']['short_name'] == 'otherRestrictions' and not uc['other_constraints']:
            errors.append(("pipeman.iso19115.legal_constraint_missing_other", "ISO19115-006"))
    return errors


def validate_time_res(tr, object_path, profile, memo):
    if not (tr['years'] or tr['months'] or tr['days'] or tr['hours'] or tr['minutes'] or tr['seconds']):
        return [("pipeman.iso19115.time_res_incomplete", "ISO19115-020")]
    return []


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
    return errors


def validate_releasability(rel, object_path, profile, memo):
    errors = []
    if not (rel['addressees'] or rel['statement']):
        errors.append(("pipeman.iso19115.releasability_requires_addressee_or_statement", "ISO19115-050"))
    return errors


def separate_keywords(keywords):
    groups = {}
    for keyword, language, thesaurus in keywords:
        title = None
        if 'citation' in thesaurus and thesaurus['citation'] and 'title' in thesaurus['citation']:
            title_field = thesaurus['citation']['title']
            if isinstance(title_field, str):
                title = title_field
            elif title_field is None:
                title = None
            else:
                test_keys = ['en', 'und']
                test_keys.extend(title_field.keys())
                for k in test_keys:
                    if k in title_field:
                        title = title_field[k]
                        break
        if title is None:
            title = ''
        if title not in groups:
            groups[title] = {
                'keywords': [],
                'thesaurus': thesaurus,
            }
        groups[title]['keywords'].append((keyword, language))
    return groups


def preprocess_metadata(dataset, **kwargs):

    locale_mapping = {}
    def_loc = dataset.data("default_locale")
    default_locale = def_loc['a2_language']
    locale_mapping[def_loc['a2_language']] = def_loc['language']
    for other_loc in dataset.data("other_locales"):
        locale_mapping[other_loc['a2_language']] = other_loc['language']
    dataset_maintenance = []
    metadata_maintenance = []
    for maintenance in dataset.data("iso_maintenance"):
        print(type(maintenance))
        if maintenance['scope']['short_name'] == "dataset":
            dataset_maintenance.append(maintenance)
        elif maintenance['scope']['short_name'] == "metadata":
            metadata_maintenance.append(maintenance)
        else:
            print(f"Unrecognized scope code: {maintenance['scope']['short_name']}")
    dataset_citation = {
        "title": dataset.data("title"),
        "identifier": dataset["doi"]["url"] if dataset["doi"] else None,
        "publication_date": dataset["publication_date"],
        "revision_date": dataset["revision_date"],
        "creation_date": dataset["creation_date"],
    }
    return {
        "default_locale": default_locale,
        "locale_mapping": locale_mapping,
        "dataset_citation": dataset_citation,
        "dataset_maintenance": dataset_maintenance,
        "metadata_maintenance": metadata_maintenance,
        "grouped_keywords": separate_keywords(dataset.keywords())
    }
