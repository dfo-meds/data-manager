import zirconium as zr
import pathlib
from autoinject import injector
import os


def _cfg_files_from_template(filename):
    custom_config_path = os.environ.get("PIPEMAN_CONFIG_DIR")
    if custom_config_path:
        p = pathlib.Path(custom_config_path)
        if p.exists():
            yield str(p / filename)
        else:
            print(f"Missing custom config directory {custom_config_path}")
    yield f"~/{filename}"
    yield f"./{filename}"


@zr.configure
def configure_pipeman(config: zr.ApplicationConfig):
    me = pathlib.Path(__file__).absolute()
    config.register_default_file(me.parent / ".pipeman.defaults.toml")
    for file in _cfg_files_from_template(".pipeman.defaults.toml"):
        config.register_default_file(file)
    for file in _cfg_files_from_template(".pipeman.toml"):
        config.register_file(file)


def init(db_only=False, extra_files=None):

    @zr.configure
    def configure_extra_files(config: zr.ApplicationConfig):
        for file in extra_files or []:
            for cfg_file in _cfg_files_from_template(file):
                config.register_file(cfg_file)

    from pipeman.util.system import System

    @injector.inject
    def _do_init(system: System = None):
        if not db_only:
            system.pre_load("pipeman.i18n.init")
            system.pre_load("pipeman.auth.init")
            system.pre_load("pipeman.core.init")
            system.init()
        return system

    return _do_init()
