from pipeman.dataset import MetadataRegistry
from pipeman.util.system import System as _System
from autoinject import injector as _injector
import pathlib

from pipeman.vocab import VocabularyRegistry
from pipeman.workflow import WorkflowRegistry


@_injector.inject
def init_plugin(system: _System):
    system.register_blueprint("pipeman.plugins.cnodc.app", "cnodc")
    system.on_setup(setup_plugin)


@_injector.inject
def setup_plugin(wreg: WorkflowRegistry = None, mreg: MetadataRegistry = None, vreg: VocabularyRegistry = None):
    root = pathlib.Path(__file__).absolute().parent
    from pipeman.auth.util import load_groups_from_yaml
    load_groups_from_yaml(root / "groups.yaml")
    wreg.register_steps_from_yaml(root / "steps.yaml")
    wreg.register_workflows_from_yaml(root / "workflows.yaml")
    mreg.register_profiles_from_yaml(root / "profiles.yaml")
    mreg.register_metadata_from_yaml(root / "metadata.yaml")
    vreg.register_from_yaml(root / "vocabs.yaml")
