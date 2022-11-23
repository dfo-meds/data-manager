from pipeman.entity import EntityRegistry
from pipeman.vocab import VocabularyRegistry
from pipeman.util import System
import pathlib
import yaml
from autoinject import injector


@injector.inject
def init_plugin(system: System = None, reg: EntityRegistry = None, vreg: VocabularyRegistry = None):
    system.register_cli("pipeman.builtins.iso19115.cli", "iso19115")
    my_parent = pathlib.Path(__file__).absolute().parent
    with open(my_parent / "entities.yaml", "r") as h:
        reg.register_from_dict(yaml.safe_load(h))
    with open(my_parent / "vocabs.yaml", "r") as h:
        vreg.register_from_dict(yaml.safe_load(h))
