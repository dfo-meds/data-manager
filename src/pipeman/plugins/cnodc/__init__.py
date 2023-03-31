from pipeman.util.system import System as _System
from autoinject import injector as _injector
import pathlib
from pipeman.workflow import WorkflowRegistry


@_injector.inject
def init_plugin(system: _System):
    system.register_blueprint("pipeman.plugins.cnodc.app", "cnodc")
    system.register_setup_fn(setup_plugin)


@_injector.inject
def setup_plugin(wreg: WorkflowRegistry = None):
    root = pathlib.Path(__file__).absolute().parent
    from pipeman.auth.util import load_groups_from_yaml
    load_groups_from_yaml(root / "groups.yaml")
    wreg.register_steps_from_yaml(root / "steps.yaml")
    wreg.register_workflows_from_yaml(root / "workflows.yaml")
