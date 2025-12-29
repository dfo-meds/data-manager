from pipeman.util.system import System as _System
from autoinject import injector as injector
import pathlib
from pipeman.dataset.dataset import MetadataRegistry


@injector.inject
def init_plugin(system: _System):
    system.on_setup(setup_plugin)


@injector.inject
def setup_plugin(mreg: MetadataRegistry = None):
    root = pathlib.Path(__file__).parent
    mreg.register_profiles_from_yaml(root / "profiles.yaml")