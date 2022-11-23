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

    tm: TranslationManager = None

    @injector.construct
    def __init__(self, text_key, default=None):
        self.text_key = text_key
        self.default = default

    def __str__(self):
        return self.tm.get_text(self.text_key, self.default)


class MultiLanguageString:

    ld: LanguageDetector = None

    @injector.construct
    def __init__(self, language_map: dict):
        self.language_map = language_map

    def __str__(self):
        lang = self.ld.detect_language(self.language_map.keys())
        return self.language_map[lang]
