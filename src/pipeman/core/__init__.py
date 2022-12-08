from autoinject import injector
from pipeman.util import caps_to_snake
from pipeman.workflow.workflow import WorkflowRegistry
import pathlib
import yaml


@injector.inject
def init(system, wreg: WorkflowRegistry = None):
    system.register_cli("pipeman.core.cli", "org")
    system.register_blueprint("pipeman.core.app", "core")
    system.register_init_app(create_jinja_filters)
    root = pathlib.Path(__file__).parent
    with open(root / "steps.yaml", "r") as h:
        wreg.register_steps_from_dict(yaml.safe_load(h))
    with open(root / "workflows.yaml", "r") as h:
        wreg.register_workflows_from_dict(yaml.safe_load(h))


def create_jinja_filters(app):
    app.jinja_env.filters['caps_to_snake'] = caps_to_snake
