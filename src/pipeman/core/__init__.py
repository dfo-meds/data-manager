from pipeman.entity import EntityRegistry
from pipeman.vocab import VocabularyRegistry
import pathlib
import yaml
from autoinject import injector


@injector.inject
def init(system, reg: EntityRegistry = None, vreg: VocabularyRegistry = None):
    system.register_cli("pipeman.core.cli", "org")
    system.register_blueprint("pipeman.core.app", "core")


