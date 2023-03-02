from autoinject import injector
from pipeman.dataset import MetadataRegistry
from pipeman.vocab import VocabularyRegistry
from pipeman.util import System
import pathlib
import yaml


@injector.inject
def init_plugin(reg: MetadataRegistry = None, vreg: VocabularyRegistry = None, system: System = None):
    root = pathlib.Path(__file__).parent
    system.register_cli("pipeman.plugins.cioos.cli", "cioos")
    with open(root / "fields.yaml", "r", encoding="utf-8") as h:
        reg.register_fields_from_dict(yaml.safe_load(h))
    with open(root / "profiles.yaml", "r", encoding="utf-8") as h:
        reg.register_profiles_from_dict(yaml.safe_load(h))
    with open(root / "vocabs.yaml", "r", encoding="utf-8") as h:
        vreg.register_from_dict(yaml.safe_load(h))
