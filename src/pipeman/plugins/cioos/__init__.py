from autoinject import injector
from pipeman.dataset import MetadataRegistry
import pathlib
import yaml


@injector.inject
def init_plugin(reg: MetadataRegistry = None):
    root = pathlib.Path(__file__).parent
    with open(root / "profiles.yaml") as h:
        reg.register_profiles_from_dict(yaml.safe_load(h))
