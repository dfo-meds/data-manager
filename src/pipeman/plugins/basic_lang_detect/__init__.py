from .detector import BasicRequestLanguageDetector
from pipeman.util.system import System as _System
from autoinject import injector as _injector
import flask


def flask_init_lang(app):
    @app.url_defaults
    def _add_lang_arg(endpoint, values):
        lang_param = flask.request.args.get("lang", "")
        if lang_param and "lang" not in values:
            values["lang"] = lang_param


@_injector.inject
def init_plugin(reg: _System = None):
    reg.register_init_app(flask_init_lang)
