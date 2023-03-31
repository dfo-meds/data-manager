from autoinject import injector
from pipeman.util import caps_to_snake
from pipeman.util import System


@injector.inject
def init(system):
    system.register_cli("pipeman.core.cli", "org")
    system.register_cli("pipeman.core.cli", "workflow")
    system.register_cli("pipeman.core.cli", "core")
    system.register_blueprint("pipeman.core.app", "base")
    system.register_blueprint("pipeman.core.app", "core")
    system.register_init_app(core_init_app)


@injector.inject
def core_init_app(app, system: System = None):
    system.register_nav_item("datasets", "pipeman.datasets", "core.list_datasets", "datasets.view")
    system.register_nav_item("entities", "pipeman.entities", "core.list_entities", "entities.view_entities")
    system.register_nav_item("action-items", "pipeman.action-items", "core.list_workflow_items", "action_items.view")
    system.register_nav_item("action-history", "pipeman.action-history", "core.list_workflow_history", "action_items.history")
    system.register_nav_item("organizations", "pipeman.organizations", "core.list_organizations", "organizations.view")
    system.register_nav_item("vocabularies", "pipeman.vocabularies", "core.list_vocabularies", "vocabularies.view")
    system.register_nav_item("home", "pipeman.home", "base.home", "_is_not_anonymous", "user", weight=-500)
    system.register_nav_item("logout", "pipeman.menu.logout", "auth.logout", "_is_not_anonymous", "user", weight=10000)
    system.register_nav_item("login", "pipeman.menu.login", "auth.login", "_is_anonymous", "user", weight=10000)
    app.jinja_env.filters['caps_to_snake'] = caps_to_snake
