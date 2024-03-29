from pipeman.entity import EntityRegistry
from pipeman.vocab import VocabularyRegistry
from pipeman.util import System
from pipeman.dataset import MetadataRegistry
import pathlib
from autoinject import injector


@injector.inject
def init_plugin(system: System = None):
    system.register_cli("pipeman.builtins.netcdf.cli", "netcdf")
    system.register_blueprint("pipeman.builtins.netcdf.app", "netcdf")
    system.on_setup("pipeman.builtins.netcdf.cli.do_update")
    system.on_setup(setup_plugin)


@injector.inject
def setup_plugin(ereg: EntityRegistry = None, vreg: VocabularyRegistry = None, mreg: MetadataRegistry = None):
    root = pathlib.Path(__file__).parent
    ereg.register_from_yaml(root / "entities.yaml")
    vreg.register_from_yaml(root / "vocabs.yaml")
    mreg.register_profiles_from_yaml(root / "profiles.yaml")
    mreg.register_metadata_from_yaml(root / "metadata.yaml")
