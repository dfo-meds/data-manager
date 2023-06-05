import logging
from autoinject import injector
from flask.sessions import SecureCookieSessionInterface, SessionMixin
from .metrics import PromMetrics, time_function
import pipeman
from pipeman.i18n import gettext
from pipeman.i18n.i18n import BaseTranslatableString
import typing as t
import datetime
import sqlalchemy as sa
from flask_wtf.csrf import CSRFProtect
import flask
import flask_login
from pipeman.util.flask import CSPRegistry, csp_nonce, csp_allow
from werkzeug.routing import Rule
import flask_autoinject
from pipeman.util.errors import PipemanConfigurationError
from pipeman.util.flask import self_url, RequestInfo
import zrlog
from pipeman.db import Database
import pipeman.db.orm as orm
import uuid
from pipeman.vocab import VocabularyRegistry
from pipeman.workflow import WorkflowRegistry
from pipeman.entity import EntityRegistry
from pipeman.dataset import MetadataRegistry
from pipeman.db.obj_registry import GlobalObjectRegistry
import ipaddress
from werkzeug.middleware.proxy_fix import ProxyFix


@injector.inject
@time_function("pipeman_setup_check_request_session", "Time to execute check_request_session()")
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
    if sess:
        zrlog.get_logger("pipeman.session").info("Invalidating session")
        with db as session:
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
    zrlog.get_logger("pipeman.session").info(f"Clearing session")
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


@time_function("pipeman_setup_build_nav", "Time to build the navigation")
def build_nav(items: dict) -> list:
    """Build a navigation menu from a list of items registered to the System object."""
    return _build_nav(items)


def _build_nav(items: dict) -> list:
    nav = []
    for x in items:
        item = items[x]
        if item["_permission"] and not (flask_login.current_user and flask_login.current_user.has_permission(item["_permission"])):
            continue
        nav.append((
            gettext(item["_label"]),
            item["_link"],
            build_nav({i: item[i] for i in item if not i.startswith("_")}),
            item["_weight"]
        ))
    nav.sort(key=lambda x: x[3])
    return nav


@injector.inject
@time_function("pipeman_setup_init_system_logging", "Time to initialize the logging")
def init_system_logging(system, rinfo: RequestInfo = None):
    # Setup logging
    zrlog.init_logging()
    zrlog.set_extras({
        "sys_username": rinfo.sys_username(),
        "sys_emulated": rinfo.sys_emulated_username(),
        "sys_logon": rinfo.sys_logon_time(),
        "sys_remote": rinfo.sys_remote_addr()
    })
    # Defaults ensure that these variables exist in all log output from now on
    zrlog.set_default_extra("sys_username", "")
    zrlog.set_default_extra("sys_emulated", "")
    zrlog.set_default_extra("sys_logon", "")
    zrlog.set_default_extra("sys_remote", "")
    zrlog.set_default_extra("username", "")
    zrlog.set_default_extra("remote_ip", "")
    zrlog.set_default_extra("proxy_ip", "")
    zrlog.set_default_extra("correlation_id", "")
    zrlog.set_default_extra("client_id", "")
    zrlog.set_default_extra("request_url", "")
    zrlog.set_default_extra("user_agent", "")
    zrlog.set_default_extra("referrer", "")
    zrlog.set_default_extra("request_method", "")
    zrlog.set_default_extra("version", pipeman.__version__)

    system.log = zrlog.get_logger("pipeman.system")


@injector.inject
@time_function("pipeman_setup_init_registries", "Time to initialize the registries")
def init_registries(r1: MetadataRegistry = None, r2: VocabularyRegistry = None, r3: WorkflowRegistry = None, r4: EntityRegistry = None):
    r1.reload_types()
    r2.reload_types()
    r3.reload_types()
    r4.reload_types()


class TrustedProxyFix:

    def __init__(self, app, trust_from_ips="*", **kwargs):
        self._app = app
        self._proxy = ProxyFix(app, **kwargs)
        self._trusted = trust_from_ips
        self._log = zrlog.get_logger("pipeman.trusted_proxy")
        self._history = {}

    @time_function("pipeman_setup_is_upstream_trustworthy", "Time to check if the upstream is trustworthy")
    def _is_upstream_trustworthy(self, environ, start_response):
        if self._trusted == "*" or self._trusted is True:
            return True
        if self._trusted == "" or self._trusted is False or self._trusted is None:
            return False
        _ip = environ.get("REMOTE_ADDR")
        try:
            upstream_ip = ipaddress.ip_address(_ip)
        except ipaddress.AddressValueError:
            self._log.warning(f"Upstream address could not be parsed: {_ip}")
            return False
        if isinstance(self._trusted, str):
            return self._match_ip_address(upstream_ip, self._trusted)
        return any(self._match_ip_address(upstream_ip, x) for x in self._trusted)

    def _match_ip_address(self, actual: ipaddress, network_def):
        try:
            subnet = ipaddress.ip_network(network_def)
            return actual in subnet
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError) as ex:
            self._log.warning(f"Trusted IP or subnet could not be parsed: {network_def}")
            return False

    def __call__(self, environ, start_response):
        """Applies proxy configuration only if the upstream IP is allowed."""
        if self._is_upstream_trustworthy(environ, start_response):
            self._log.debug("trusting upstream...")
            return self._proxy(environ, start_response)
        else:
            self._log.debug("not trusting upstream...")
            return self._app(environ, start_response)


class SessionCookieInterface(SecureCookieSessionInterface):

    @injector.inject
    def should_set_cookie(self, app: "Flask", session: SessionMixin, cspr: CSPRegistry = None) -> bool:
        return not (cspr.allow_caching() and cspr.allow_shared_caching())


def stable_dict_key_list(d: dict):
    keys = list(d.keys())
    keys.sort()
    return keys


@injector.inject
def core_init_app(system, app, config, prom_metrics: PromMetrics = None):
    #app.session_interface = SessionCookieInterface()
    if "flask" in config:
        app.config.update(config["flask"] or {})
    if not app.config.get("SECRET_KEY"):
        raise PipemanConfigurationError("Secret key for Flask must be defined")
    prom_metrics.init_app(app)
    flask_autoinject.init_app(app)
    # Set the URL Rule class to our custom one
    app.url_rule_class = CustomRule
    if isinstance(app.config["SECRET_KEY"], str):
        app.config["SECRET_KEY"] = app.config["SECRET_KEY"].encode("ascii")
    # Adjust the user timeout as necessary
    system.user_timeout = config.as_int(("pipeman", "session_expiry"), default=44640)
    app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(minutes=system.user_timeout + 1)
    system.log.info(f"Usertime set to {system.user_timeout} seconds")
    if config.as_bool(("pipeman", "proxy_fix", "enabled"), default=False):
        system.log.info("Proxy fix: enabled")
        app.wsgi_app = TrustedProxyFix(
            app.wsgi_app,
            trust_from_ips=config.get(("pipeman", "proxy_fix", "trusted_upstreams"), default="*"),
            x_for=config.get(("pipeman", "proxy_fix", "x_for"), default=1),
            x_proto=config.get(("pipeman", "proxy_fix", "x_proto"), default=1),
            x_host=config.get(("pipeman", "proxy_fix", "x_host"), default=1),
            x_port=config.get(("pipeman", "proxy_fix", "x_port"), default=1),
            x_prefix=config.get(("pipeman", "proxy_fix", "x_prefix"), default=1)
        )
    else:
        system.log.info("Proxy fix: disabled")

    # Before request, make sure the session is permanent
    @app.before_request
    @injector.inject
    @time_function("pipeman_setup_session_init", "Time to start the before request stuff")
    def session_init(rinfo: RequestInfo = None, cspr: CSPRegistry = None):
        if flask.request.endpoint == "static":
            cspr.set_static()
        #check_request_session()
        zrlog.set_extras({
            "username": rinfo.username(),
            "remote_ip": rinfo.remote_ip(),
            "proxy_ip": rinfo.proxy_ip(),
            "correlation_id": rinfo.correlation_id(),
            "client_id": rinfo.client_id(),
            "request_url": rinfo.request_url(),
            "user_agent": rinfo.user_agent(),
            "referrer": rinfo.referrer(),
            "request_method": rinfo.request_method(),
        })

    system.access_log = zrlog.get_logger("pipeman.access_log")

    # After the request, perform a few clean-up tasks
    @app.after_request
    @injector.inject
    @time_function("pipeman_setup_add_response_headers", "Time to cleanup the request")
    def add_response_headers(response: flask.Response, cspr: CSPRegistry = None):
        cspr.add_csp_policy('img-src', 'https://cdn.datatables.net')
        if flask.request.endpoint == "static":
            # Avoid spamming crap into the log for every static resource
            system.access_log.debug(
                f"{flask.request.method} \"{flask.request.url}\" {response.status_code}"
            )
        else:
            system.access_log.notice(
                f"{flask.request.method} \"{flask.request.url}\" {response.status_code}"
            )
        response = cspr.add_headers(response)
        return response

    @app.teardown_request
    @injector.inject
    def refresh_object_registry(exc, gor: GlobalObjectRegistry = None):
        try:
            gor.check_all()
        except Exception as ex:
            zrlog.get_logger("pipeman.teardown").exception("Error while refreshing object registry")

    # Add the menu items and self_url() function to every template
    @app.context_processor
    def add_menu_item():
        items = {
            'self_url': self_url,
            'csp_nonce': csp_nonce,
            'csp_allow': csp_allow,
            'stable_dict_key_list': stable_dict_key_list,
            'is_multilingual_map': is_multilingual_map,
        }
        for key in system._nav_menu:
            items[f'nav_{key}'] = build_nav(system._nav_menu[key])
        return items

    app.extensions['csrf'] = CSRFProtect(app)


def is_multilingual_map(obj):
    return isinstance(obj, dict) or isinstance(obj, BaseTranslatableString)


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
