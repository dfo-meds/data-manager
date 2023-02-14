from autoinject import injector
from pipeman.util import caps_to_snake
from pipeman.workflow.workflow import WorkflowRegistry
from pipeman.dataset import MetadataRegistry
from pipeman.vocab import VocabularyRegistry
from pipeman.files import DataStoreRegistry
from pipeman.entity import EntityRegistry
import pathlib
import yaml


@injector.inject
def init_plugin(reg: MetadataRegistry = None, vreg: VocabularyRegistry = None, ereg: EntityRegistry = None):
    root = pathlib.Path(__file__).parent
    with open(root / "vocabs.yaml", "r") as h:
        vreg.register_from_dict(yaml.safe_load(h))
    with open(root / "entities.yaml", "r") as h:
        ereg.register_from_dict(yaml.safe_load(h))
    with open(root / "fields.yaml") as h:
        reg.register_fields_from_dict(yaml.safe_load(h))

