from pipeman.i18n import TranslationManager
from autoinject import injector


class PipemanError(Exception):

    pass


class TranslatableError(PipemanError):

    tm: TranslationManager = None

    @injector.construct
    def __init__(self, error_str_key, *subs):
        super().__init__(self.tm.get_text(error_str_key) % subs)


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
