from autoinject import injector
from pipeman.i18n.i18n import LanguageDetector, TranslationManager, DelayedTranslationString, MultiLanguageString, MultiLanguageLink
from jinja2 import pass_context
import functools


def gettext(text_key: str, default_text: str = None) -> DelayedTranslationString:
    return DelayedTranslationString(text_key, default_text)


@injector.inject
def format_datetime(dt, format_str: str = "pipeman.formats.datetime", na_str="pipeman.general.na", default_format="%Y-%m-%d %H:%M:%S", tm: TranslationManager = None):
    if dt is None:
        return gettext(na_str)
    else:
        return dt.strftime(tm.get_text(format_str, default_format))


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


def _i18n_sort(to_sort, *, key=None, reverse=False, insensitive=True, language_order=None):
    order_me = list(to_sort)
    if language_order is None:
        language_order = ["und", "en"]
    order_me.sort(key=lambda x: _i18n_sort_key(x, key, language_order, insensitive), reverse=reverse)
    return order_me


def _i18n_sort_key(x, key, language_order, ignore_case):
    if key is not None:
        if callable(key):
            x = key(x)
        else:
            x = x[key]
    if x is None:
        return ""
    if isinstance(x, str):
        return x if not ignore_case else x.lower()
    for lang in language_order:
        if lang in x and x[lang]:
            return x[lang] if not ignore_case else x[lang].lower()
    for lang in x.keys():
        if x[lang]:
            return x[lang] if not ignore_case else x[lang].lower()
    return ""


def add_lang_cb(app):
    @app.context_processor
    @injector.inject
    def add_lang_variable(ld: LanguageDetector = None, tm: TranslationManager = None):
        language = ld.detect_language(tm.supported_languages())
        return {
            'language': language,
            "i18n_sort": functools.partial(_i18n_sort, language_order=[language, "und"])
        }


def init(system):
    system.register_init_app(create_jinja_filters)
    system.register_init_app(add_lang_cb)
    system.register_cli("pipeman.i18n.cli", "i18n")
