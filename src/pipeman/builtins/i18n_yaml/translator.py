import yaml
import os
from autoinject import injector
from pipeman.i18n import LanguageDetector
import zirconium as zr
import logging


class YamlTranslationManager:

    ld: LanguageDetector = None
    cfg: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self, dictionary_path: str = None):
        if dictionary_path is None:
            dictionary_path = self.cfg.as_path(('pipeman', 'i18n_yaml', 'dictionary_path'))
        self.log = logging.getLogger("pipeman.i18n_yaml")
        self._warn_on_missing_key = self.cfg.as_bool(('pipeman', 'i18n_yaml', 'warn_missing_key'), default=False)
        self._dictionaries = {}
        self._dictionary_lookup = {}
        for file in os.scandir(dictionary_path):
            if file.name.endswith(".yaml") or file.name.endswith(".yml"):
                self._dictionary_lookup[file.name[:file.name.rfind(".")]] = file.path
        self._supported = None

    def supported_languages(self):
        if not self._supported:
            self._supported = list(self._dictionary_lookup.keys())
        return self._supported

    def _ensure_dictionary(self, lang):
        if lang not in self._dictionaries:
            with open(self._dictionary_lookup[lang], "r", encoding="utf-8") as h:
                self._dictionaries[lang] = yaml.safe_load(h)
                if self._dictionaries[lang] is None:
                    self._dictionaries[lang] = {}

    def get_text(self, text_key: str, default: str = None) -> str:
        lang = self.ld.detect_language(self.supported_languages())
        if not lang:
            self.log.error(f"Could not find a supported language, options {'|'.join(self.supported_languages())}")
            raise ValueError("Could not agree on a language")
        self._ensure_dictionary(lang)
        if text_key not in self._dictionaries[lang]:
            if self._warn_on_missing_key:
                self.log.warning(f"Missing language key {text_key} for {lang}")
            return text_key if default is None else default
        return self._dictionaries[lang][text_key]
