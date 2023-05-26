from pipeman.i18n import TranslationManager, DelayedTranslationString
from autoinject import injector


class PipemanError(Exception):

    pass


class TranslatableError(PipemanError):

    tm: TranslationManager = None

    @injector.construct
    def __init__(self, error_str_key, *subs, **kwargs):
        super().__init__(DelayedTranslationString(error_str_key, None, *subs, **kwargs))


class FormValueError(ValueError, PipemanError):

    def __init__(self, error_str):
        super(ValueError, self).__init__(DelayedTranslationString(error_str))


class MetadataError(PipemanError):

    tm: TranslationManager = None

    @injector.construct
    def __init__(self, error_str_key, field_name):
        super.__init__(f"{self.tm.get_text(error_str_key)}: {field_name}")


class UserInputError(TranslatableError):
    pass


class DataTypeNotSupportedError(PipemanError):
    pass


class EntityNotFoundError(PipemanError):
    pass


class DatasetNotFoundError(PipemanError):
    pass


class StepNotFoundError(PipemanError):
    pass


class StepConfigurationError(PipemanError):
    pass


class WorkflowNotFoundError(PipemanError):
    pass


class WorkflowItemNotFoundError(PipemanError):
    pass


class DataStoreNotFoundError(PipemanError):
    pass


class PipemanConfigurationError(PipemanError):
    pass


class _WrapperError(PipemanError):

    def __init__(self, msg="", ex=None):
        super().__init__(msg)


class RecoverableError(_WrapperError):
    pass


class UnrecoverableError(_WrapperError):
    pass


class TranslationNotAvailableYet(RecoverableError):
    pass
