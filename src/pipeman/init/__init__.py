import zirconium as zr
import pathlib
from autoinject import injector
import os
import logging


def _config_paths():
    yield pathlib.Path(".").absolute()
    yield pathlib.Path("~").absolute().expanduser()
    custom_config_path = os.environ.get("PIPEMAN_CONFIG_SEARCH_PATHS", "./config")
    if custom_config_path:
        paths = custom_config_path.split(";")
        for path in paths:
            if path:
                p = pathlib.Path(path)
                if p.exists():
                    yield p


def init(db_only=False, extra_files=None):

    @zr.configure
    def configure_extra_files(config: zr.ApplicationConfig):
        config_paths = [x for x in _config_paths()]
        for path in config_paths:
            config.register_default_file(path / ".pipeman.defaults.toml")
            config.register_file(path / ".pipeman.toml")
            for filename in extra_files or []:
                config.register_file(path / filename)

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
