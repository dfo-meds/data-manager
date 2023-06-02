"""Utilities for managing plugins and system-wide initialization."""
from autoinject import injector
from autoinject.informants import NamedContextInformant
import zirconium as zr
import importlib
import pkgutil
import pathlib
import typing as t
from pipeman.util.errors import PipemanConfigurationError
import threading
import zrlog


CallableOrStr = t.Union[callable, str]


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
        self._hooks = {}
        self._flask_blueprints = []
        self._click_groups = []
        self._nav_menu = {}
        self._user_nav_menu = {}
        self.i18n_dirs = set()
        self.user_timeout = 0
        self.i18n_locale_dirs = []
        self.log = None
        self._nci = None
        self._lock = threading.RLock()

    def on(self, event_name: str, cb: CallableOrStr):
        """Register an event callback function"""
        with self._lock:
            if event_name not in self._hooks:
                self._hooks[event_name] = []
            self._hooks[event_name].append(cb)

    def fire(self, event_name: str, *args, **kwargs):
        """Call all registered event callback functions with the given arguments"""
        self.log.debug(f"Firing {event_name}")
        if event_name in self._hooks:
            for cb in self._hooks[event_name]:
                if isinstance(cb, str):
                    obj = load_object(cb)
                    obj(*args, **kwargs)
                else:
                    cb(*args, **kwargs)

    def init(self):
        """Initialize the application for the first time."""
        # Setup a named context to manage the setup vs request workflows
        self._nci = NamedContextInformant("pipeman_stage")
        self._nci.switch_context("init")
        injector.register_informant(self._nci)

        # System logging
        from pipeman.util.setup import init_system_logging, init_registries
        init_system_logging(self)
        self.log.out("Initializing system")

        # Pre-init functions
        self.fire("init.before", self)

        # Include plugins
        self.log.debug("Loading plugins...")
        self._init_plugins()

        # Manage overrides
        self.log.debug("Setting up autoinject overrides")
        self._init_overrides()

        # Set up the translation directories
        self.log.debug("Initializing locale directories")
        root = pathlib.Path(__file__).absolute().parent.parent
        self.i18n_dirs.update([
            str(root),
            str(pathlib.Path(".").absolute() / "templates"),
        ])

        # Reloading registeries
        self.log.debug("Loading registries")
        init_registries()

        # Call the init callbacks
        self.fire("init")

        # Post-load callback
        self.fire("init.after")

        self.log.out("Init complete")

    def on_cron_start(self, cb: CallableOrStr):
        self.on("cron.start", cb)

    def on_cron(self, cb: CallableOrStr):
        self.on("cron", cb)

    def pre_setup(self, cb: CallableOrStr):
        self.on("setup.before", cb)

    def on_setup(self, setup_cb: CallableOrStr):
        """Register a function to call on setup."""
        self.on("setup", setup_cb)

    def post_setup(self, cb: CallableOrStr):
        self.on("setup.after", cb)

    def on_app_init(self, init_app_cb: CallableOrStr):
        """Register a function to call when init_app() is called."""
        self.on("init.app", init_app_cb)

    def on_cli_init(self, init_cli_cb: CallableOrStr):
        """Register a function to call when init_cli() is called."""
        self.on("init.cli", init_cli_cb)

    def pre_load(self, load_cb: CallableOrStr):
        """Register a function to call at the start of init()."""
        self.on("init.before", load_cb)

    def on_load(self, load_cb: CallableOrStr):
        """Register a function to call during init()."""
        self.on("init", load_cb)

    def post_load(self, load_cb: CallableOrStr):
        self.on("init.after", load_cb)

    def pre_cleanup(self, cleanup_cb: CallableOrStr):
        """Register a function to call at the start of cleanup()."""
        self.on("cleanup.before", cleanup_cb)

    def on_cleanup(self, cleanup_cb: CallableOrStr):
        """Register a function to call during cleanup()."""
        self.on("cleanup", cleanup_cb)

    def post_cleanup(self, cleanup_cb: CallableOrStr):
        self.on("cleanup.after", cleanup_cb)
        
    def setup(self):
        """Run all the setup scripts."""
        self.fire("setup.before")
        self.fire("setup")
        self.fire("setup.after")

    def cleanup(self):
        """Run all the cleanup scripts."""
        self.fire("cleanup.before")
        self.fire("cleanup")
        self.fire("cleanup.after")

    def register_blueprint(self, module: str, blueprint_name: str, prefix: str = ""):
        """Register a blueprint to add to the main Flask application."""
        if prefix and not prefix.startswith("/"):
            prefix = f"/{prefix}"
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

    def init_app(self, app):
        """Initialize a Flask application."""
        from pipeman.util.setup import core_init_app

        self.fire("init.app.before")

        # Load the Flask-specific configuration from the main config item
        core_init_app(self, app, self.config)

        # Call all of the init methods registered by plugins
        self.fire("init.app", app)

        universal_prefix = self.config.get(("pipeman", "base_path"), default="")
        if universal_prefix:
            if not universal_prefix.startswith("/"):
                universal_prefix = f"/{universal_prefix}"

        # Load all of the blueprints registered by plugins
        for bp_mod, bp_obj, prefix in self._flask_blueprints:
            mod = importlib.import_module(bp_mod)
            bp = getattr(mod, bp_obj)
            app.register_blueprint(bp, url_prefix=f"{universal_prefix}{prefix}")

        self.fire("init.app.after")

        # We want to kill the init context here so that we can save on resources
        self._nci.switch_context("flask_app")
        self._nci.destroy("init")

        return app

    def init_cli(self, _app):
        """Initialize the main click command."""
        from pipeman.cli import CommandLineInterface

        self.init_app(_app)

        self.fire("init.cli.before")

        # Register all the command groups provided by plugins
        commands = {}
        for bp_mod, bp_obj, reg_name in self._click_groups:
            mod = importlib.import_module(bp_mod)
            commands[reg_name] = getattr(mod, bp_obj)

        # Build the main group
        cli = CommandLineInterface(_app, commands)

        # Allow modifications, if necessary
        self.fire("init.cli", cli)

        self.fire("init.cli.after")

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
        self.log.out(f"Plugins initialized: {','.join(self._short_plugins)}")

    def _load_plugin(self, name: str):
        """Load a plugin from its fully qualified name."""
        if name not in self.plugins:
            self.log.debug(f"Loading plugin {name}")
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
            self.log.debug(f"Plugin {name} loaded")

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


