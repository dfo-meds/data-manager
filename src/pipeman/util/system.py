"""Utilities for managing plugins and system-wide initialization."""
import logging
import flask
import flask_login
from autoinject import injector
import zirconium as zr
import importlib
import zrlog
import pkgutil
from pipeman.i18n import gettext
import pathlib
from flask import session, render_template
from flask_wtf.csrf import CSRFProtect
import flask_autoinject
from pipeman.util.flask import self_url
from werkzeug.routing import Rule
import typing as t
import datetime
from pipeman.util.logging import PipemanLogger
from pipeman.util.errors import PipemanConfigurationError
from pipeman.util.flask import CSPRegistry, csp_nonce, csp_allow
from autoinject.informants import NamedContextInformant


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


def load_dynamic_class(cls_name: str) -> object:
    """Instantiate an instance of a class from its fully qualified class name."""
    return load_object(cls_name)()


def load_object(obj_name: str) -> t.Any:
    """Find and return a class/function/variable by its fully qualified name."""
    package_dot_pos = obj_name.rfind(".")
    package = obj_name[0:package_dot_pos]
    specific_cls_name = obj_name[package_dot_pos + 1:]
    mod = importlib.import_module(package)
    return getattr(mod, specific_cls_name)


@injector.injectable_global
class System:
    """Core management of plugins and configuration."""

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self.plugins = set()
        self._short_plugins = set()
        self.globals = {}
        self._load_init = []
        self._flask_init_cb = []
        self._setup_cb = []
        self._pre_init = []
        self._cli_init_cb = []
        self._flask_blueprints = []
        self._click_groups = []
        self._nav_menu = {}
        self._user_nav_menu = {}
        self.i18n_dirs = set()
        self.user_timeout = 0
        self.i18n_locale_dirs = []
        self._log = None
        self._nci = None

    def init(self):
        """Initialize the application for the first time."""
        # Setup a named context to manage the setup vs request workflows
        self._nci = NamedContextInformant("pipeman_stage")
        self._nci.switch_context("init")
        injector.register_informant(self._nci)
        # Setup logging
        zrlog.init_logging()
        logging.setLoggerClass(PipemanLogger)
        self._log = logging.getLogger("pipeman.system")
        self._log.out("Initializing system")
        # Pre-init functions
        for obj_name in self._pre_init:
            obj = load_object(obj_name)
            obj(self)
        # Include plugins
        self._init_plugins()
        # Manage overrides
        self._init_overrides()
        # Set up the translation directories
        root = pathlib.Path(__file__).absolute().parent.parent
        self.i18n_dirs.update([
            str(root),
            str(pathlib.Path(".").absolute() / "templates"),
        ])
        # Call the init callbacks
        for fn in self._load_init:
            fn()
        self._log.out("Init complete")

    def register_setup_fn(self, setup_cb: callable):
        """Register a function to call on setup."""
        self._setup_cb.append(setup_cb)

    def register_init_app(self, init_app_cb: callable):
        """Register a function to call when init_app() is called."""
        self._flask_init_cb.append(init_app_cb)

    def register_init_cli(self, init_cli_cb: callable):
        """Register a function to call when init_cli() is called."""
        self._cli_init_cb.append(init_cli_cb)

    def pre_load(self, load_cb: str):
        """Register a function to call at the start of init()."""
        self._pre_init.append(load_cb)

    def on_load(self, load_cb: callable):
        """Register a function to call when init() is done."""
        self._load_init.append(load_cb)

    def setup(self):
        """Run all the setup scripts."""
        for cb in self._setup_cb:
            obj = load_object(cb)
            obj()

    def register_blueprint(self, module: str, blueprint_name: str, prefix: str = ""):
        """Register a blueprint to add to the main Flask application."""
        self._flask_blueprints.append((module, blueprint_name, prefix))

    def register_cli(self, module: str, group_name: str, register_as: str = None):
        """Register a click command group to add to the main CLI application."""
        if register_as is None:
            register_as = group_name
        self._click_groups.append((module, group_name, register_as))

    def register_nav_item(self, hierarchy: str, item_text: str, item_link: str, permission: str, nav_group: str = 'main', weight: t.Optional[int] = None):
        """Register navigational menu items to the main Flask application."""
        levels = hierarchy.split(".")
        levels.reverse()
        if nav_group not in self._nav_menu:
            self._nav_menu[nav_group] = {}
        working = self._nav_menu[nav_group]
        while len(levels) > 1:
            nxt = levels.pop()
            if nxt in working:
                working = working[nxt]
            else:
                working[nxt] = {}
        working[levels[0]] = {
            "_label": item_text,
            "_link": item_link,
            "_permission": permission,
            "_weight": len(working) if weight is None else weight
        }

    def init_app(self, app: flask.Flask):
        """Initialize a Flask application."""
        flask_autoinject.init_app(app)
        # Set the URL Rule class to our custom one
        app.url_rule_class = CustomRule

        CSRFProtect(app)

        # Load the Flask-specific configuration from the main config item
        if "flask" in self.config:
            app.config.update(self.config["flask"])

        if not app.config.get("SECRET_KEY"):
            raise PipemanConfigurationError("Secret key for Flask must be defined")

        if isinstance(app.config["SECRET_KEY"], str):
            app.config["SECRET_KEY"] = app.config["SECRET_KEY"].encode("ascii")

        # Adjust the user timeout as necessary
        self.user_timeout = self.config.as_int(("pipeman", "session_expiry"), default=44640)
        app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(minutes=self.user_timeout + 1)

        # Call all of the init methods registered by plugins
        for cb in self._flask_init_cb:
            cb(app)

        # Load all of the blueprints registered by plugins
        for bp_mod, bp_obj, prefix in self._flask_blueprints:
            mod = importlib.import_module(bp_mod)
            bp = getattr(mod, bp_obj)
            app.register_blueprint(bp, url_prefix=prefix)

        # Before request, make sure the session is permanent
        @app.before_request
        def make_session_permanent():
            session.permanent = True
            session.modified = True
            logging.getLogger("pipeman").info(f"Request context: {injector.context_manager._get_context_hash()}")

        # After the request, perform a few clean-up tasks
        @app.after_request
        @injector.inject
        def add_response_headers(response, cspr: CSPRegistry = None):
            return cspr.add_headers(response)

        # Add the menu items and self_url() function to every template
        @app.context_processor
        def add_menu_item():
            items = {
                'self_url': self_url,
                'csp_nonce': csp_nonce,
                'csp_allow': csp_allow,
            }
            for key in self._nav_menu:
                items[f'nav_{key}'] = self._build_nav(self._nav_menu[key])
            return items

        # Main home page for logged in users (the welcome page)
        @app.route("/h")
        def home():
            return render_template("welcome.html", title=gettext("pipeman.welcome.title"))

        # The splash page welcomes new users
        @app.route("/")
        def splash():
            return render_template("splash.html")

        # We want to kill the init context here so that we can save on resources
        self._nci.switch_context("flask_app")
        self._nci.destroy("init")

        return app

    def init_cli(self):
        """Initialize the main click command."""
        from pipeman.cli import CommandLineInterface

        # Register all the command groups provided by plugins
        commands = {}
        for bp_mod, bp_obj, reg_name in self._click_groups:
            mod = importlib.import_module(bp_mod)
            commands[reg_name] = getattr(mod, bp_obj)

        # Build the main group
        cli = CommandLineInterface(commands)

        # Allow modifications, if necessary
        for cb in self._cli_init_cb:
            cb(cli)

        return cli

    def _init_plugins(self):
        """Find and initialize all of the plugins."""
        import pipeman.plugins as plg
        import pipeman.builtins as int_plg
        # These ones should not be loaded
        skip_load = self.config.get(("pipeman", "plugins", "skip"), default=None) or []
        # These ones must be loaded last, in the order given
        delayed_load = self.config.get(("pipeman", "plugins", "last"), default=None) or []
        # First priority loads, in the order given
        for name in self.config.get(("pipeman", "plugins", "first"), default=None) or []:
            if name not in delayed_load and name not in skip_load:
                self._load_plugin(name)
        # Next, all built-in plugins unless delayed or skipped
        for _, name, _ in pkgutil.iter_modules(int_plg.__path__, "pipeman.builtins."):
            if name not in delayed_load and name not in skip_load:
                self._load_plugin(name)
        # Next, all actual plugins unless delayed or skipped
        for _, name, _ in pkgutil.iter_modules(plg.__path__, "pipeman.plugins."):
            if name not in delayed_load and name not in skip_load:
                self._load_plugin(name)
        # Lastly, all the deplayed plugins
        for name in delayed_load:
            self._load_plugin(name)
        self._log.out(f"Plugins initialized: {','.join(self._short_plugins)}")

    def _load_plugin(self, name: str):
        """Load a plugin from its fully qualified name."""
        if name not in self.plugins:
            self._log.debug(f"Loading plugin {name}")
            # Import it
            mod = importlib.import_module(name)
            # Call init_plugin() if it exists
            if hasattr(mod, "init_plugin"):
                getattr(mod, "init_plugin")()
            # Store it in the list
            self.plugins.add(name)
            name_pieces = name.split(".")
            sname = ".".join(name_pieces[2:])
            self._short_plugins.add(sname)
            self._log.debug(f"Plugin {name} loaded")

    def _init_overrides(self):
        """Override default objects with declared sub-classes as required."""
        injections = self.config.get("autoinject", default=None)
        if injections:
            for cls_name in injections:
                cls_def = injections[cls_name]
                if isinstance(cls_def, str):
                    injector.override(cls_name, cls_def, weight=1)
                elif isinstance(cls_def, dict):
                    # This is a dictionary which should contain a "constructor" entry at least
                    if "constructor" not in cls_def:
                        raise PipemanConfigurationError(f"Class definition for {cls_name} is missing a constructor entry")
                    a = cls_def.pop("args") if "args" in cls_def else []
                    if "weight" not in cls_def:
                        cls_def["weight"] = 1
                    injector.override(cls_name, cls_def.pop("constructor"), *a, **cls_def)

    def _build_nav(self, items: dict) -> list:
        """Build a navigation menu from a list of items registered to the System object."""
        nav = []
        for x in items:
            item = items[x]
            if item["_permission"] and not flask_login.current_user.has_permission(item["_permission"]):
                continue
            nav.append((
                gettext(item["_label"]),
                item["_link"],
                self._build_nav({i: item[i] for i in item if not i.startswith("_")}),
                item["_weight"]
            ))
        nav.sort(key=lambda x: x[3])
        return nav
