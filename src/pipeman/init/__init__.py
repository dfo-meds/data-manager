import zirconium as zr
import pathlib
from autoinject import injector


@zr.configure
def configure_pipeman(config: zr.ApplicationConfig):
    me = pathlib.Path(__file__)
    config.register_default_file(me.parent / ".pipeman.defaults.toml")
    config.register_file("./.pipeman.toml")
    config.register_file("~/.pipeman.toml")


def init(db_only=False, extra_files=None):

    @zr.configure
    def configure_extra_files(config: zr.ApplicationConfig):
        if extra_files:
            for file in extra_files:
                config.register_file(file)

    from pipeman.util.system import System
    from pipeman.auth import init as auth_init
    from pipeman.core import init as core_init
    from pipeman.i18n import init as i18n_init

    @injector.inject
    def _do_init(system: System = None):
        if not db_only:
            i18n_init(system)
            auth_init(system)
            core_init(system)
            system.init()
        return system

    return _do_init()
