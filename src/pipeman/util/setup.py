import logging
from autoinject import injector
import zirconium as zr
import importlib
import zrlog
import pkgutil
from pipeman.i18n import gettext
import pathlib
import typing as t
import datetime
from autoinject.informants import NamedContextInformant
from flask import session, render_template
from flask_wtf.csrf import CSRFProtect
import flask
import flask_login
from pipeman.util.flask import CSPRegistry, csp_nonce, csp_allow
from werkzeug.routing import Rule
import flask_autoinject
from pipeman.util.logging import PipemanLogger
from pipeman.util.errors import PipemanConfigurationError

from pipeman.util.flask import self_url


def build_nav(items: dict) -> list:
    """Build a navigation menu from a list of items registered to the System object."""
    nav = []
    for x in items:
        item = items[x]
        if item["_permission"] and not flask_login.current_user.has_permission(item["_permission"]):
            continue
        nav.append((
            gettext(item["_label"]),
            item["_link"],
            build_nav({i: item[i] for i in item if not i.startswith("_")}),
            item["_weight"]
        ))
    nav.sort(key=lambda x: x[3])
    return nav

def init_system_logging(system):
    # Setup logging
    zrlog.init_logging()
    logging.setLoggerClass(PipemanLogger)
    system._log = logging.getLogger("pipeman.system")


def core_init_app(system, app, config):
    if "flask" in config:
        app.config.update(config["flask"] or {})
    if not app.config.get("SECRET_KEY"):
        raise PipemanConfigurationError("Secret key for Flask must be defined")
    flask_autoinject.init_app(app)
    # Set the URL Rule class to our custom one
    app.url_rule_class = CustomRule
    app.extensions['csrf'] = CSRFProtect(app)
    if isinstance(app.config["SECRET_KEY"], str):
        app.config["SECRET_KEY"] = app.config["SECRET_KEY"].encode("ascii")
    # Adjust the user timeout as necessary
    system.user_timeout = config.as_int(("pipeman", "session_expiry"), default=44640)
    app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(minutes=system.user_timeout + 1)

    # Before request, make sure the session is permanent
    @app.before_request
    def make_session_permanent():
        session.permanent = True
        session.modified = True
        logging.getLogger("pipeman").out(f"Request context: {injector.context_manager._get_context_hash()}")

    # After the request, perform a few clean-up tasks
    @app.after_request
    @injector.inject
    def add_response_headers(response, cspr: CSPRegistry = None):
        cspr.add_csp_policy('img-src', 'https://cdn.datatables.net')
        return cspr.add_headers(response)

    # Add the menu items and self_url() function to every template
    @app.context_processor
    def add_menu_item():
        items = {
            'self_url': self_url,
            'csp_nonce': csp_nonce,
            'csp_allow': csp_allow,
        }
        for key in system._nav_menu:
            items[f'nav_{key}'] = build_nav(system._nav_menu[key])
        return items


class CustomRule(Rule):
    """Custom implementation of werkzeug.routing.Rule.

    This implementation accepts the additional accept_languages and ignore_languages parameters which allow the
    selection of an ideal URL based on the URLs it is most suitable for.

    In essence, a Rule which has accept_languages set will ONLY be chosen for those languages. A Rule which has
    ignore_languages set will NEVER be chosen for those languages. In practice, we can use this to make
    language-specific Rules, e.g.:

    @app.route("/accueil", accept_languages="fr")   # Only used when the language is FR
    @app.route("/home", ignore_languages="fr")      # Not used when the language is FR
    def home():
        return "homepage"

    To ensure at least one route is viable for each endpoint, it is recommended to put the default language as one
    which ignores all the other languages which have their URLs set specifically as given in the example above where
    the English URL is the default for any language which is not French.
    """

    ld: "pipeman.i18n.i18n.LanguageDetector" = None
    tm: "pipeman.i18n.i18n.TranslationManager" = None

    @injector.construct
    def __init__(self,
                 *args,
                 accept_languages: t.Optional[t.Union[str, t.Iterable]] = None,
                 ignore_languages: t.Optional[t.Union[str, t.Iterable]] = None,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self._accept_languages = [accept_languages] if isinstance(accept_languages, str) else accept_languages
        self._ignore_languages = [ignore_languages] if isinstance(ignore_languages, str) else ignore_languages

    def suitable_for(
        self,
        values: t.Mapping[str, t.Any],
        method: t.Optional[str] = None
    ) -> bool:
        if not super().suitable_for(values, method):
            return False
        if not (self._ignore_languages or self._accept_languages):
            return True
        lang = "und"
        if "lang" in values:
            lang = values["lang"]
        elif flask.has_request_context():
            lang = self.ld.detect_language(self.tm.supported_languages())
        if self._ignore_languages and lang in self._ignore_languages:
            return False
        return lang in self._accept_languages if self._accept_languages else True
