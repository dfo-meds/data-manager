from autoinject import injector
from pipeman.util import System
import zirconium as zr
import zrlog


@injector.inject
def init_plugin(system: System = None, cfg: zr.ApplicationConfig = None):
    te_cls = cfg.as_str(("autoinject", "pipeman.i18n.workflow.TranslationEngine"), default=None)
    if te_cls == "pipeman.builtins.mtrans.mtrans.ManualTranslationEngine":
        zrlog.get_logger("pipeman.mtrans").notice(f"Enabling manual translation endpoints")
        system.register_blueprint("pipeman.builtins.mtrans.endpoints", "mtrans")
        system.register_nav_item("download_translations", "menu.download_translations", "mtrans.download_translations", "translations.manage", weight=10000)
        system.register_nav_item("upload_translations", "menu.upload_translations", "mtrans.upload_translations", "translations.manage", weight=10001)
