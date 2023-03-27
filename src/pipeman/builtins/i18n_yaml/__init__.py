from .translator import YamlTranslationManager
from pipeman.util import System
from autoinject import injector
from zirconium import ApplicationConfig


@injector.inject
def init_plugin(system: System = None, cfg: ApplicationConfig = None):
    dictionary_paths = cfg.get(('pipeman', 'i18n_yaml', 'dictionary_paths'))
    if dictionary_paths:
        if isinstance(dictionary_paths, list):
            system.i18n_locale_dirs.extend(dictionary_paths)
        else:
            system.i18n_locale_dirs.append(dictionary_paths)
