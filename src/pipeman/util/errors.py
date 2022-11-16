from pipeman.i18n import TranslationManager
from autoinject import injector


class TranslatableError(Exception):

    tm: TranslationManager = None

    @injector.construct
    def __init__(self, error_str_key, *subs):
        super().__init__(self.tm.get_text(error_str_key) % subs)


class UserInputError(TranslatableError):
    pass
