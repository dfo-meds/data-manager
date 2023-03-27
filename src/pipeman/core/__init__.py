import flask_login
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
def init(system, reg: MetadataRegistry = None, wreg: WorkflowRegistry = None, vreg: VocabularyRegistry = None, dsr: DataStoreRegistry = None, ereg: EntityRegistry = None):
    system.register_cli("pipeman.core.cli", "org")
    system.register_cli("pipeman.core.cli", "workflow")
    system.register_cli("pipeman.core.cli", "core")
    system.register_blueprint("pipeman.core.app", "base")
    system.register_blueprint("pipeman.core.app", "core")
    system.register_init_app(create_jinja_filters)
    system.register_setup_fn("pipeman.core.util.setup_core_groups")
    system.register_nav_item("datasets", "pipeman.datasets", "core.list_datasets", "datasets.view")
    system.register_nav_item("entities", "pipeman.entities", "core.list_entities", "entities.view_entities")
    system.register_nav_item("action-items", "pipeman.action-items", "core.list_workflow_items", "action_items.view")
    system.register_nav_item("organizations", "pipeman.organizations", "core.list_organizations", "organizations.view")
    system.register_nav_item("vocabularies", "pipeman.vocabularies", "core.list_vocabularies", "vocabularies.view")
    system.register_nav_item("home", "pipeman.home", "base.home", "_is_not_anonymous", "user", weight=-500)
    system.register_nav_item("logout", "pipeman.menu.logout", "auth.logout", "_is_not_anonymous", "user", weight=10000)
    system.register_nav_item("login", "pipeman.menu.login", "auth.login", "_is_anonymous", "user", weight=10000)

    root = pathlib.Path(__file__).parent
    with open(root / "steps.yaml", "r", encoding="utf-8") as h:
        wreg.register_steps_from_dict(yaml.safe_load(h))
    with open(root / "workflows.yaml", "r", encoding="utf-8") as h:
        wreg.register_workflows_from_dict(yaml.safe_load(h))
    with open(root / "security.yaml", "r", encoding="utf-8") as h:
        reg.register_security_labels_from_dict(yaml.safe_load(h))
    with open(root / "vocabs.yaml", "r", encoding="utf-8") as h:
        vreg.register_from_dict(yaml.safe_load(h))
    with open(root / "entities.yaml", "r", encoding="utf-8") as h:
        ereg.register_from_dict(yaml.safe_load(h))
    with open(root / "fields.yaml", encoding="utf-8") as h:
        reg.register_fields_from_dict(yaml.safe_load(h))
    dsr.register_data_store("test-store", {"en": "Test Store"}, "C:/my/local_store", True, 'basic', 'basic', True)


def create_jinja_filters(app):
    app.jinja_env.filters['caps_to_snake'] = caps_to_snake
