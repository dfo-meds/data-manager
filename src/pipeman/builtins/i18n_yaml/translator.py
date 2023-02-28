import yaml
import os
from autoinject import injector
from pipeman.i18n import LanguageDetector
import zirconium as zr


class YamlTranslationManager:

    ld: LanguageDetector = None
    cfg: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self, dictionary_path: str = None):
        if dictionary_path is None:
            dictionary_path = self.cfg.as_path(('pipeman', 'i18n_yaml', 'dictionary_path'))
        self._dictionaries = {}
        self._dictionary_lookup = {}
        for file in os.scandir(dictionary_path):
            if file.name.endswith(".yaml") or file.name.endswith(".yml"):
                self._dictionary_lookup[file.name[:file.name.rfind(".")]] = file.path

    def supported_languages(self):
        return self._dictionary_lookup.keys()

    def _ensure_dictionary(self, lang):
        if lang not in self._dictionaries:
            with open(self._dictionary_lookup[lang], "r", encoding="utf-8") as h:
                self._dictionaries[lang] = yaml.safe_load(h)
                if self._dictionaries[lang] is None:
                    self._dictionaries[lang] = {}

    def get_text(self, text_key: str, default: str = None) -> str:
        lang = self.ld.detect_language(self.supported_languages())
        if not lang:
            raise ValueError("Could not agree on a language")
        self._ensure_dictionary(lang)
        if text_key not in self._dictionaries[lang]:
            return text_key if default is None else default
        return self._dictionaries[lang][text_key]
