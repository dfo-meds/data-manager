from autoinject import injector
from pipeman.i18n.i18n import LanguageDetector, TranslationManager, DelayedTranslationString, MultiLanguageString
from jinja2 import pass_context


@injector.inject
def gettext(text_key: str, default_text: str = None, tm: TranslationManager = None) -> str:
    return tm.get_text(text_key, default_text)


def format_datetime(dt, format_str: str = "pipeman.formats.datetime", na_str="pipeman.general.na", default_format="%Y-%m-%d %H:%M:%S"):
    if dt is None:
        return gettext(na_str)
    else:
        return dt.strftime(gettext(format_str, default_format))


def format_date(dt, format_str: str = "pipeman.formats.date", na_str="pipeman.general.na", default_format="%Y-%m-%d"):
    return format_datetime(dt, format_str, na_str, default_format)


def _jinja_context_wrapper(func):

    @pass_context
    def _do_wrap(ctx, *args, **kwargs):
        return func(*args, **kwargs)

    return _do_wrap


def create_jinja_filters(app):
    app.jinja_env.filters["gettext"] = _jinja_context_wrapper(gettext)
    app.jinja_env.filters["format_date"] = _jinja_context_wrapper(format_date)
    app.jinja_env.filters["format_datetime"] = _jinja_context_wrapper(format_datetime)


def init(system):
    system.register_init_app(create_jinja_filters)
    system.register_cli("pipeman.i18n.cli", "i18n")
