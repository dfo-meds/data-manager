"""Basic language detection module"""
from .detector import BasicRequestLanguageDetector
from pipeman.util.system import System as _System
from pipeman.util.flask import self_url
from autoinject import injector as _injector
from pipeman.i18n import LanguageDetector, TranslationManager, gettext
import markupsafe
import flask

__all__ = ["BasicRequestLanguageDetector"]


@_injector.inject
def flask_init_lang(app, ld: LanguageDetector = None, tm: TranslationManager = None):
    """Initialize the Flask application to detect languages."""
    supported_languages = tm.supported_languages()

    @app.url_defaults
    def _add_lang_arg(endpoint, values):
        """Add the language parameter."""
        if endpoint == 'static':
            # Don't add to static requests, these are raw files
            return
        lang_param = ld.detect_language(supported_languages)
        if lang_param and "lang" not in values:
            values["lang"] = markupsafe.escape(lang_param)

    @app.context_processor
    def _add_language_links():
        """Add language links to the context of each page."""
        current_lang = ld.detect_language(supported_languages)
        ctx = {
            "language_switchers": {}
        }
        for lang in supported_languages:
            link = self_url(lang=lang)
            ctx["language_switchers"][lang] = (gettext(f"language_names.{lang}"), link, current_lang != lang)
        return ctx


@_injector.inject
def init_plugin(reg: _System = None):
    """Register the application init function."""
    reg.register_init_app(flask_init_lang)
