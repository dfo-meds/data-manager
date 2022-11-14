from autoinject import injector
import zirconium as zr
import importlib
import zrlog
import pkgutil


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

    def init(self):
        zrlog.init_logging()
        self.init_plugins()
        self._init_overrides()

    def _init_overrides(self):
        for cls_name in self.config["injections"]:
            cls_def = self.config["injections"][cls_name]
            if isinstance(cls_def, str):
                injector.override(cls_name, cls_def, weight=1)
            else:
                a = cls_def.pop("args") if "args" in cls_def else []
                if "weight" not in cls_def:
                    cls_def["weight"] = 1
                injector.override(cls_name, cls_def.pop("constructor"), *a, **cls_def)

    def register_init_app(self, init_app_cb):
        self._flask_init_cb.append(init_app_cb)

    def register_init_cli(self, init_cli_cb):
        self._cli_init_cb.append(init_cli_cb)

    def register_blueprint(self, module, blueprint_name, prefix=""):
        self._flask_blueprints.append((module, blueprint_name, prefix))

    def init_plugins(self):
        import pipeman.plugins as plg
        for _, name, _ in pkgutil.iter_modules(plg.__path__, "pipeman.plugins."):
            if name not in self.plugins:
                mod = importlib.import_module(name)
                if hasattr(mod, "init_plugin"):
                    getattr(mod, "init_plugin")()
                self.plugins.add(name)

    def init_app(self, app):
        if "flask" in self.config:
            app.config.update(self.config["flask"])
        for cb in self._flask_init_cb:
            cb(app)
        for bp_mod, bp_obj, prefix in self._flask_blueprints:
            mod = importlib.import_module(bp_mod)
            bp = getattr(mod, bp_obj)
            app.register_blueprint(bp, url_prefix=prefix)
        return app

    def init_cli(self):
        from pipeman.cli import base
        for cb in self._cli_init_cb:
            cb(base)
        return base
