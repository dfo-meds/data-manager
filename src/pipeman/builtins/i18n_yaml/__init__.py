from .translator import YamlTranslationManager
from pipeman.util import System
from autoinject import injector
from zirconium import ApplicationConfig


@injector.inject
def init_plugin(system: System = None, cfg: ApplicationConfig = None):
    dictionary_path = cfg.as_path(('pipeman', 'i18n_yaml', 'dictionary_path'))
    if dictionary_path:
        system.i18n_locale_dirs.append(dictionary_path)
