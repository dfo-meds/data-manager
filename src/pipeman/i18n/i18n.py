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

    @injector.inject
    def __str__(self, tm: TranslationManager = None, ld: LanguageDetector = None):
        lang = ld.detect_language(self.language_map.keys())
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
