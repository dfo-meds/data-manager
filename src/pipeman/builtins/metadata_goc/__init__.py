from autoinject import injector
from pipeman.dataset import MetadataRegistry
from pipeman.vocab import VocabularyRegistry
from pipeman.entity import EntityRegistry
import pathlib
import yaml
import csv


@injector.inject
def init_plugin(reg: MetadataRegistry = None, vreg: VocabularyRegistry = None, ereg: EntityRegistry = None):
    root = pathlib.Path(__file__).parent
    with open(root / "vocabs.yaml", "r", encoding="utf-8") as h:
        vreg.register_from_dict(yaml.safe_load(h))
    with open(root / "entities.yaml", "r", encoding="utf-8") as h:
        ereg.register_from_dict(yaml.safe_load(h))
    with open(root / "fields.yaml", "r", encoding="utf-8") as h:
        reg.register_fields_from_dict(yaml.safe_load(h))
    with open(root / "profiles.yaml", "r", encoding="utf-8") as h:
        reg.register_profiles_from_dict(yaml.safe_load(h))
    with open(root / "places.csv", "r", encoding="utf-8") as h:
        reader = csv.reader(h)
        place_terms = {}
        for row in reader:
            if row:
                key = row[0].strip(" ")
                if key:
                    place_terms[key] = {
                        "display": {
                            "en": row[0],
                            "fr": row[1]
                        }
                    }
        vreg.register_terms_from_dict("goc_places", place_terms)
