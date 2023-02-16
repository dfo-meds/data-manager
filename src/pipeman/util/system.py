import flask_login
from autoinject import injector
import zirconium as zr
import importlib
import zrlog
import pkgutil
from pipeman.i18n import gettext
import pathlib
from flask import session
import datetime


def load_dynamic_class(cls_name):
    package_dot_pos = cls_name.rfind(".")
    package = cls_name[0:package_dot_pos]
    specific_cls_name = cls_name[package_dot_pos+1:]
    mod = importlib.import_module(package)
    return getattr(mod, specific_cls_name)()


@injector.injectable
class System:

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self.plugins = set()
        self.globals = {}
        self._flask_init_cb = []
        self._cli_init_cb = []
        self._flask_blueprints = []
        self._click_groups = []
        self._nav_menu = {}
        self._user_nav_menu = {}
        self.i18n_dirs = set()
        self.user_timeout = 0

    def init(self):
        zrlog.init_logging()
        self.init_plugins()
        self._init_overrides()
        root = pathlib.Path(__file__).absolute().parent.parent
        self.i18n_dirs.update([
            str(root),
            str(pathlib.Path(".").absolute() / "templates"),
        ])

    def _init_overrides(self):
        injections = self.config.get("autoinject", default=None)
        if injections:
            for cls_name in injections:
                cls_def = injections[cls_name]
                if isinstance(cls_def, str):
                    injector.override(cls_name, cls_def, weight=1)
                else:
                    a = cls_def.pop("args") if "args" in cls_def else []
                    if "weight" not in cls_def:
                        cls_def["weight"] = 1
                    injector.override(cls_name, cls_def.pop("constructor"), *a, **cls_def)

    def register_nav_item(self, hierarchy, item_text, item_link, permission, nav_group='main'):
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
            "_permission": permission
        }

    def _build_nav(self, items):
        nav = []
        for x in items:
            item = items[x]
            if item["_permission"] and not flask_login.current_user.has_permission(item["_permission"]):
                continue
            nav.append((
                gettext(item["_label"]),
                item["_link"],
                self._build_nav({i: item[i] for i in item if not i.startswith("_")})
            ))
        return nav

    def register_init_app(self, init_app_cb):
        self._flask_init_cb.append(init_app_cb)

    def register_init_cli(self, init_cli_cb):
        self._cli_init_cb.append(init_cli_cb)

    def register_blueprint(self, module, blueprint_name, prefix=""):
        self._flask_blueprints.append((module, blueprint_name, prefix))

    def register_cli(self, module, group_name, register_as=None):
        if register_as is None:
            register_as = group_name
        self._click_groups.append((module, group_name, register_as))

    def init_plugins(self):
        import pipeman.plugins as plg
        import pipeman.builtins as int_plg
        delayed_load = self.config.get(("pipeman", "plugins", "last"), default=[])
        for name in self.config.get(("pipeman", "plugins", "first"), default=[]):
            if name not in delayed_load:
                self._load_plugin(name)
        for _, name, _ in pkgutil.iter_modules(int_plg.__path__, "pipeman.builtins."):
            if name not in delayed_load:
                self._load_plugin(name)
        for _, name, _ in pkgutil.iter_modules(plg.__path__, "pipeman.plugins."):
            if name not in delayed_load:
                self._load_plugin(name)
        for name in delayed_load:
            self._load_plugin(name)

    def _load_plugin(self, name):
        if name not in self.plugins:
            mod = importlib.import_module(name)
            if hasattr(mod, "init_plugin"):
                getattr(mod, "init_plugin")()
            self.plugins.add(name)

    def init_app(self, app):
        @app.before_request
        def make_session_permanent():
            session.permanent = True
            session.modified = True
        if "flask" in self.config:
            app.config.update(self.config["flask"])
        self.user_timeout = self.config.as_int(("pipeman", "session_expiry"), default=44640)
        app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(minutes=self.user_timeout + 1)

        for cb in self._flask_init_cb:
            cb(app)
        for bp_mod, bp_obj, prefix in self._flask_blueprints:
            mod = importlib.import_module(bp_mod)
            bp = getattr(mod, bp_obj)
            app.register_blueprint(bp, url_prefix=prefix)

        @app.teardown_request
        @injector.inject
        def kill_db_session(exc):
            # Make sure we get the local (at the time) instance
            db = injector.get("pipeman.db.db.Database")
            db.close()

        @app.context_processor
        def add_menu_item():
            items = {}
            for key in self._nav_menu:
                items[f'nav_{key}'] = self._build_nav(self._nav_menu[key])
            return items

        return app

    def init_cli(self):
        from pipeman.cli import CommandLineInterface
        commands = {}
        for bp_mod, bp_obj, reg_name in self._click_groups:
            mod = importlib.import_module(bp_mod)
            commands[reg_name] = getattr(mod, bp_obj)
        cli = CommandLineInterface(commands)
        for cb in self._cli_init_cb:
            cb(cli)
        return cli
