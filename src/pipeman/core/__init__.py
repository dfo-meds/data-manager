from autoinject import injector
from pipeman.util import caps_to_snake


@injector.inject
def init(system):
    system.register_cli("pipeman.core.cli", "org")
    system.register_blueprint("pipeman.core.app", "core")
    system.register_init_app(create_jinja_filters)


def create_jinja_filters(app):
    app.jinja_env.filters['caps_to_snake'] = caps_to_snake
