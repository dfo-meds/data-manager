
def separate_keywords(keywords):
    groups = {}
    for keyword, language, thesaurus in keywords:
        print(keyword)
        print(thesaurus)
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
                print(test_keys)
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
        print(title)
        groups[title]['keywords'].append((keyword, language))
        print(groups)
    print("done")
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
