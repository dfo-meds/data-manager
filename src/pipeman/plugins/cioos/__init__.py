from autoinject import injector
from pipeman.dataset import MetadataRegistry
from pipeman.vocab import VocabularyRegistry
from pipeman.util import System
import pathlib
import yaml


@injector.inject
def init_plugin(system: System = None):
    root = pathlib.Path(__file__).parent
    system.register_cli("pipeman.plugins.cioos.cli", "cioos")
    system.register_setup_fn("pipeman.plugins.cioos.cli.do_update")
    system.register_setup_fn(setup_plugin)


@injector.inject
def setup_plugin(vreg: VocabularyRegistry = None, reg: MetadataRegistry = None):
    root = pathlib.Path(__file__).absolute().parent
    vreg.register_from_yaml(root / "vocabs.yaml")
    reg.register_profiles_from_yaml(root / "profiles.yaml")
    reg.register_metadata_from_yaml(root / "metadata.yaml")
