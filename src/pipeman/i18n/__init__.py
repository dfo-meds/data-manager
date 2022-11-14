from autoinject import injector
from pipeman.i18n.i18n import LanguageDetector, TranslationManager, DelayedTranslationString, MultiLanguageString


@injector.inject
def gettext(text_key: str, default_text: str = None, tm: TranslationManager = None) -> str:
    return tm.get_text(text_key, default_text)
