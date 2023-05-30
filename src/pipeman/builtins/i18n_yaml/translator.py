import yaml
import os
from autoinject import injector
from pipeman.i18n import LanguageDetector, TranslationManager
import logging
import typing as t


class YamlTranslationManager(TranslationManager):

    ld: LanguageDetector = None

    @injector.construct
    def __init__(self, extra_paths: t.Union[str, t.Iterable, None] = None):
        self._allow_undefined = self.cfg.get(("pipeman", "i18n_yaml", "allow_undefined"), default=False)
        self.log = logging.getLogger("pipeman.i18n_yaml")
        dpaths = []
        if isinstance(extra_paths, str):
            dpaths.append(extra_paths)
        elif extra_paths is not None:
            dpaths.extend(extra_paths)
        cfg_paths = self.cfg.get(('pipeman', 'i18n_yaml', 'dictionary_paths'), default=None)
        if isinstance(cfg_paths, str):
            dpaths.append(cfg_paths)
        elif cfg_paths is not None:
            dpaths.extend(cfg_paths)
        self._warn_on_missing_key = self.cfg.as_bool(('pipeman', 'i18n_yaml', 'warn_missing_key'), default=False)
        self._dictionaries = {}
        self._dictionary_lookup = {}
        for dict_path in dpaths:
            if not os.path.exists(dict_path):
                continue
            for file in os.scandir(dict_path):
                if file.name.endswith(".yaml") or file.name.endswith(".yml"):
                    self._dictionary_lookup[file.name[:file.name.rfind(".")]] = file.path
        self._supported = []
        if self._allow_undefined:
            self._supported = ["und"]
        self._supported.extend(list(self._dictionary_lookup.keys()))

    def supported_languages(self):
        return self._supported

    def _ensure_dictionary(self, lang):
        if lang not in self._dictionaries:
            with open(self._dictionary_lookup[lang], "r", encoding="utf-8") as h:
                self._dictionaries[lang] = yaml.safe_load(h)
                if self._dictionaries[lang] is None:
                    self._dictionaries[lang] = {}

    def get_text(self, text_key: str, default: str = None) -> str:
        lang = self.ld.detect_language(self.supported_languages())
        if lang == "und":
            return default or text_key
        if not lang:
            self.log.error(f"Could not find a supported language, options {'|'.join(self.supported_languages())}")
            raise ValueError("Could not agree on a language")
        self._ensure_dictionary(lang)
        if text_key not in self._dictionaries[lang]:
            if self._warn_on_missing_key:
                self.log.warning(f"Missing language key {text_key} for {lang}")
            return text_key if default is None else default
        return self._dictionaries[lang][text_key]
