from autoinject import injector


@injector.injectable_global
class LanguageDetector:

    def detect_language(self, supported_languages) -> str:
        return 'en'


@injector.injectable_global
class TranslationManager:

    def get_text(self, text_key: str, default: str = None) -> str:
        return default if default is not None else text_key

    def supported_languages(self):
        return ['en', 'fr']


class DelayedTranslationString:

    def __init__(self, text_key, default=None):
        self.text_key = text_key
        self.default = default

    @injector.inject
    def __str__(self, tm: TranslationManager):
        return tm.get_text(self.text_key, self.default)


class MultiLanguageString:

    def __init__(self, language_map: dict, default_lang="en"):
        self.language_map = language_map
        self.default_lang = default_lang
        if not self.language_map:
            raise ValueError("Language required")

    @injector.inject
    def render(self, language=None, tm: TranslationManager = None, ld: LanguageDetector = None):
        lang_opts = list(self.language_map.keys())
        lang = language if language is not None and language in lang_opts else ld.detect_language(lang_opts)
        use_blank = lang in self.language_map
        if lang in self.language_map and self.language_map[lang]:
            return self.language_map[lang]
        if "und" in self.language_map and self.language_map["und"]:
            return self.language_map["und"]
        if use_blank:
            return ""
        if self.default_lang in self.language_map:
            return self.language_map[self.default_lang]
        return tm.get_text("pipeman.general.unknown")

    def __call__(self, language=None):
        return self.render(language)

    def __html__(self):
        return self.render()

    def __str__(self):
        return self.render()

    def __getitem__(self, key):
        return self.render(key)

