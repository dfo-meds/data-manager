import zirconium as zr
import pathlib
from autoinject import injector


@zr.configure
def configure_pipeman(config: zr.ApplicationConfig):
    me = pathlib.Path(__file__)
    config.register_default_file(me.parent / ".pipeman.defaults.toml")
    config.register_file("./.pipeman.yaml")
    config.register_file("./.pipeman.toml")
    config.register_file("~/.pipeman.yaml")
    config.register_file("~/.pipeman.toml")


def init():
    from pipeman.util.system import System
    from pipeman.auth import init as auth_init

    @injector.inject
    def _do_init(system: System = None):
        auth_init(system)
        system.init()
        return system

    return _do_init()
