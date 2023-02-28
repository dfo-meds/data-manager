from pipeman.entity import EntityRegistry
from pipeman.vocab import VocabularyRegistry
from pipeman.util import System
from pipeman.dataset import MetadataRegistry
import pathlib
import yaml
from autoinject import injector


@injector.inject
def init_plugin(system: System = None, reg: EntityRegistry = None, vreg: VocabularyRegistry = None, mreg: MetadataRegistry = None):
    system.register_cli("pipeman.builtins.iso19115.cli", "iso19115")
    system.register_blueprint("pipeman.builtins.iso19115.app", "iso19115")
    my_parent = pathlib.Path(__file__).absolute().parent
    with open(my_parent / "entities.yaml", "r", encoding="utf-8") as h:
        reg.register_from_dict(yaml.safe_load(h))
    with open(my_parent / "vocabs.yaml", "r", encoding="utf-8") as h:
        vreg.register_from_dict(yaml.safe_load(h))
    with open(my_parent / "fields.yaml", "r", encoding="utf-8") as h:
        mreg.register_fields_from_dict(yaml.safe_load(h))
    with open(my_parent / "profiles.yaml", "r", encoding="utf-8") as h:
        mreg.register_profiles_from_dict(yaml.safe_load(h))
