import logging

from autoinject import injector
import typing as t


class PipemanError(Exception):
    pass


class TranslatableError(PipemanError):

    def __init__(self, error_str_key, *subs, **kwargs):
        from pipeman.i18n.i18n import DelayedTranslationString
        super().__init__(DelayedTranslationString(error_str_key, None, *subs, **kwargs))


class FormValueError(ValueError, PipemanError):

    def __init__(self, error_str):
        from pipeman.i18n.i18n import DelayedTranslationString
        super(ValueError, self).__init__(DelayedTranslationString(error_str))


from pipeman.i18n.i18n import TranslationManager

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


class APIInputError(PipemanError):
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


def recoverable_batch_step(cb: t.Callable) -> t.Callable:
    def _wrapper(step, context, *args, **kwargs):
        try:
            return cb(step, context, *args, **kwargs)
        except RecoverableError as e:
            step.output.append(str(e))
            logging.getLogger("pipeman.batch_errors").exception("attempting to recover from exception: %s [%s]", str(e), step.item.id)
            from pipeman.workflow.steps import ItemResult
            return ItemResult.BATCH_DELAY
    return _wrapper