from autoinject import injector
from pipeman.dataset import MetadataRegistry
from pipeman.vocab import VocabularyRegistry
from pipeman.entity import EntityRegistry
from pipeman.util import System
import pathlib


@injector.inject
def init_plugin(system: System = None):
    system.register_blueprint("pipeman.builtins.erddap.app", "erddap")
    system.on_setup(setup_plugin)


@injector.inject
def setup_plugin(ereg: EntityRegistry = None, vreg: VocabularyRegistry = None, reg: MetadataRegistry = None):
    root = pathlib.Path(__file__).parent
    ereg.register_from_yaml(root / "entities.yaml")
    vreg.register_from_yaml(root / "vocabs.yaml")
    reg.register_metadata_from_yaml(root / "metadata.yaml")
    reg.register_profiles_from_yaml(root / "profiles.yaml")
