from autoinject import injector
from pipeman.i18n.i18n import LanguageDetector, TranslationManager, DelayedTranslationString, MultiLanguageString
from jinja2 import pass_context


@injector.inject
def gettext(text_key: str, default_text: str = None, tm: TranslationManager = None) -> str:
    return tm.get_text(text_key, default_text)


def _jinja_context_wrapper(func):

    @pass_context
    def _do_wrap(ctx, *args, **kwargs):
        return func(*args, **kwargs)

    return _do_wrap


def create_jinja_filters(app):
    app.jinja_env.filters["gettext"] = _jinja_context_wrapper(gettext)


def init(system):
    system.register_init_app(create_jinja_filters)
