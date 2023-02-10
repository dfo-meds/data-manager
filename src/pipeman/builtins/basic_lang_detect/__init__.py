from .detector import BasicRequestLanguageDetector
from pipeman.util.system import System as _System
from autoinject import injector as _injector
from pipeman.i18n import LanguageDetector, TranslationManager, gettext
import flask


@_injector.inject
def flask_init_lang(app, ld: LanguageDetector = None, tm: TranslationManager = None):
    supported_languages = tm.supported_languages()

    @app.url_defaults
    def _add_lang_arg(endpoint, values):
        lang_param = flask.request.args.get("lang", "")
        if lang_param and "lang" not in values:
            values["lang"] = lang_param

    @app.context_processor
    def _add_language_links():
        current_lang = ld.detect_language(supported_languages)
        ctx = {
            "language_switchers": {}
        }
        for lang in supported_languages:
            # TODO: should update second parameter to be the full language link to the current page
            ctx["language_switchers"][lang] = (gettext(f"language_names.{lang}"), f"?lang={lang}", current_lang != lang)
        return ctx


@_injector.inject
def init_plugin(reg: _System = None):
    reg.register_init_app(flask_init_lang)
