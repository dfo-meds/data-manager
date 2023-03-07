import flask
from pipeman.i18n import gettext
from pipeman.util.flask import MultiLanguageBlueprint

dfo = MultiLanguageBlueprint("dfo", __name__)


@dfo.i18n_route("/help")
def help():
    return _render_dfo_template("dfo_help", gettext("dfo.help.title"))


def _render_dfo_template(template_base_name, title):
    lang = flask.request.args.get('lang', default='en')
    if lang not in ('en', 'fr'):
        lang = 'en'
    return flask.render_template(f"{template_base_name}_{lang}.html", title=title)
