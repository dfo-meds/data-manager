from pipeman.util import System
from pipeman.entity import EntityRegistry
from pipeman.vocab import VocabularyRegistry
from pipeman.workflow import WorkflowRegistry
from pipeman.dataset import MetadataRegistry
from autoinject import injector
import pathlib


def init(system: System):
    system.register_setup_fn(setup_module)


@injector.inject
def setup_module(
        ereg: EntityRegistry = None,
        vreg: VocabularyRegistry = None,
        wreg: WorkflowRegistry = None,
        mreg: MetadataRegistry = None
):
    from pipeman.auth.util import load_groups_from_yaml
    root_path = pathlib.Path(__file__).absolute().parent
    ereg.register_from_yaml(root_path / "entities.yaml")
    vreg.register_from_yaml(root_path / "vocabs.yaml")
    wreg.register_workflows_from_yaml(root_path / "workflows.yaml")
    wreg.register_steps_from_yaml(root_path / "steps.yaml")
    mreg.register_metadata_from_yaml(root_path / "metadata.yaml")
    mreg.register_security_labels_from_yaml(root_path / "security.yaml")
    load_groups_from_yaml(root_path / "groups.yaml")


# gettext('pipeman.label.witem.type.receive_send_item')
# gettext('pipeman.label.witem.type.send_file')
# gettext('pipeman.label.witem.type.dataset_publication')
# gettext('pipeman.label.witem.type.dataset_activation')
