import logging
from autoinject import injector
import zrlog
from pipeman.i18n import gettext
import typing as t
import datetime
import sqlalchemy as sa
from flask_wtf.csrf import CSRFProtect
import flask
import flask_login
from pipeman.util.flask import CSPRegistry, csp_nonce, csp_allow
from werkzeug.routing import Rule
import flask_autoinject
from pipeman.util.logging import PipemanLogger
from pipeman.util.errors import PipemanConfigurationError
from pipeman.util.flask import self_url, RequestInfo
from pipeman.util.logging import set_request_info
from pipeman.db import Database
import pipeman.db.orm as orm
import uuid


@injector.inject
def check_request_session(db: Database = None):
    if flask.request.endpoint == "static":
        return
    sess = flask.session.get("_pipeman_uuid", default=None)
    with db as session:
        if sess is None:
            _new_session(session)
        else:
            user_session = session.query(orm.ServerSession).filter_by(guid=sess).first()
            if not _validate_session(user_session):
                _new_session(session)
            else:
                _refresh_session(user_session, session)


@injector.inject
def invalidate_session(db: Database = None):
    sess = flask.session.get("_pipeman_uuid", default=None)
    with db as session:
        if sess:
            session.query(orm.ServerSession).filter_by(guid=sess).delete()
            session.commit()
        _new_session(session)


def _refresh_session(user_session, session):
    user_session.valid_until = datetime.datetime.now() + flask.current_app.permanent_session_lifetime
    session.commit()
    flask.session.permanent = True
    flask.session.modified = True


def _validate_session(user_session):
    if user_session is None:
        return False
    if not user_session.is_valid:
        return False
    if user_session.valid_until < datetime.datetime.now():
        return False
    return True


def _new_session(session):
    # new session
    flask.session.clear()
    flask.session["_pipeman_uuid"] = str(uuid.uuid4())
    q = sa.insert(orm.ServerSession).values({
        "guid": flask.session["_pipeman_uuid"],
        "valid_until": datetime.datetime.now() + flask.current_app.permanent_session_lifetime,
        "is_valid": True
    })
    session.execute(q)
    session.commit()
    flask.session.permanent = True
    flask.session.modified = True


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
    if isinstance(app.config["SECRET_KEY"], str):
        app.config["SECRET_KEY"] = app.config["SECRET_KEY"].encode("ascii")
    # Adjust the user timeout as necessary
    system.user_timeout = config.as_int(("pipeman", "session_expiry"), default=44640)
    app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(minutes=system.user_timeout + 1)

    # Before request, make sure the session is permanent
    @app.before_request
    @injector.inject
    def make_session_permanent(rinfo: RequestInfo = None):
        check_request_session()
        set_request_info(
            rinfo.username(),
            rinfo.remote_ip()
        )
        logging.getLogger("pipeman").debug(f"Request context: {injector.context_manager._get_context_hash()}")

    # After the request, perform a few clean-up tasks
    @app.after_request
    @injector.inject
    def add_response_headers(response: flask.Response, cspr: CSPRegistry = None):
        cspr.add_csp_policy('img-src', 'https://cdn.datatables.net')
        if flask.request.endpoint == "static":
            logging.getLogger("pipeman.access_log").info(
                f"{flask.request.method} \"{flask.request.url}\" {response.status_code}"
            )
        else:
            logging.getLogger("pipeman.access_log").out(
                f"{flask.request.method} \"{flask.request.url}\" {response.status_code}"
            )
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

    app.extensions['csrf'] = CSRFProtect(app)


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
