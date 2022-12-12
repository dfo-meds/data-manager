from autoinject import injector
from pipeman.util import caps_to_snake
from pipeman.workflow.workflow import WorkflowRegistry
from pipeman.dataset import MetadataRegistry
from pipeman.vocab import VocabularyRegistry
import pathlib
import yaml


@injector.inject
def init(system, reg: MetadataRegistry = None, wreg: WorkflowRegistry = None, vreg: VocabularyRegistry = None):
    system.register_cli("pipeman.core.cli", "org")
    system.register_blueprint("pipeman.core.app", "core")
    system.register_init_app(create_jinja_filters)
    system.register_nav_item("datasets", "pipeman.datasets", "core.list_datasets", "datasets.view")
    system.register_nav_item("entities", "pipeman.entities", "core.list_entities", "entities.view_entities")
    system.register_nav_item("action-items", "pipeman.action-items", "core.list_workflow_items", "action_items.view")
    root = pathlib.Path(__file__).parent
    with open(root / "steps.yaml", "r") as h:
        wreg.register_steps_from_dict(yaml.safe_load(h))
    with open(root / "workflows.yaml", "r") as h:
        wreg.register_workflows_from_dict(yaml.safe_load(h))
    with open(root / "security.yaml", "r") as h:
        reg.register_security_labels_from_dict(yaml.safe_load(h))
    with open(root / "vocabs.yaml", "r") as h:
        vreg.register_from_dict(yaml.safe_load(h))


def create_jinja_filters(app):
    app.jinja_env.filters['caps_to_snake'] = caps_to_snake
