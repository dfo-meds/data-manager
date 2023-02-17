from autoinject import injector
from pipeman.dataset import MetadataRegistry
from pipeman.vocab import VocabularyRegistry
from pipeman.entity import EntityRegistry
from pipeman.util import System
import pathlib
import yaml


@injector.inject
def init_plugin(system: System = None, reg: MetadataRegistry = None, vreg: VocabularyRegistry = None, ereg: EntityRegistry = None):
    system.register_blueprint("pipeman.builtins.erddap.app", "erddap")
    root = pathlib.Path(__file__).parent
    with open(root / "vocabs.yaml", "r") as h:
        vreg.register_from_dict(yaml.safe_load(h))
    with open(root / "entities.yaml", "r") as h:
        ereg.register_from_dict(yaml.safe_load(h))
    with open(root / "fields.yaml") as h:
        reg.register_fields_from_dict(yaml.safe_load(h))
    with open(root / "profiles.yaml") as h:
        reg.register_profiles_from_dict(yaml.safe_load(h))
