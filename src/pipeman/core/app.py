import flask
import flask_login
from autoinject import injector
from pipeman.entity import EntityController, EntityRegistry
from pipeman.dataset import DatasetController
from pipeman.auth import require_permission

core = flask.Blueprint("core", __name__)


@core.route("/objects")
@require_permission("entities.view_entities")
@injector.inject
def list_entities(reg: EntityRegistry):
    entity_list = []
    for k in reg:
        if flask_login.current_user.has_permission(f"entities.view.{k}"):
            entity_list.append((
                k,
                reg.display(k),
                flask.url_for("core.list_entities_by_type", obj_type=k),
                flask.url_for("core.create_entity", obj_type=k)
            ))
    return flask.render_template("list_entity_types.html", entity_types=entity_list)


@core.route("/objects/<obj_type>")
@require_permission("entities.view_entities")
@injector.inject
def list_entities_by_type(obj_type, con: EntityController):
    if not con.reg.type_exists(obj_type):
        return flask.abort(404)
    if not con.has_access(obj_type, "view"):
        return flask.abort(403)
    return con.list_entities_page(obj_type)


@core.route("/objects/<obj_type>/new", methods=["POST", "GET"])
@require_permission("entities.create")
@injector.inject
def create_entity(obj_type, con: EntityController = None):
    if not con.reg.type_exists(obj_type):
        return flask.abort(404)
    if not con.has_access(obj_type, "create"):
        return flask.abort(403)
    return con.create_entity_form(obj_type)


@core.route("/objects/<obj_type>/<obj_id>")
@require_permission("entities.view")
@injector.inject
def view_entity(obj_type, obj_id, con: EntityController = None):
    if not con.reg.type_exists(obj_type):
        return flask.abort(404)
    if not con.has_access(obj_type, "view"):
        return flask.abort(403)
    return con.view_entity_page(obj_type, obj_id)


@core.route("/objects/<obj_type>/<obj_id>/edit", methods=["POST", "GET"])
@require_permission("entities.edit")
@injector.inject
def edit_entity(obj_type, obj_id, con: EntityController = None):
    if not con.reg.type_exists(obj_type):
        return flask.abort(404)
    if not con.has_access(obj_type, "edit"):
        return flask.abort(403)
    return con.edit_entity_form(obj_type, obj_id)


@core.route("/objects/<obj_type>/<obj_id>/remove", methods=["POST", "GET"])
@require_permission("entities.remove")
@injector.inject
def remove_entity(obj_type, obj_id, con: EntityController = None):
    if not con.reg.type_exists(obj_type):
        return flask.abort(404)
    if not con.has_access(obj_type, "remove"):
        return flask.abort(403)
    return con.remove_entity_form(obj_type, obj_id)


@core.route("/objects/<obj_type>/<obj_id>/restore", methods=["POST", "GET"])
@require_permission("entities.restore")
@injector.inject
def restore_entity(obj_type, obj_id, con: EntityController = None):
    if not con.reg.type_exists(obj_type):
        return flask.abort(404)
    if not con.has_access(obj_type, "restore"):
        return flask.abort(403)
    return con.restore_entity_form(obj_type, obj_id)


@core.route("/datasets")
@require_permission("datasets.view")
@injector.inject
def list_datasets(con: DatasetController = None):
    pass


@core.route("/datasets/new", methods=["POST", "GET"])
@require_permission("datasets.create")
@injector.inject
def create_dataset(con: DatasetController = None):
    pass


@core.route("/datasets/<dataset_id>")
@require_permission("datasets.view")
@injector.inject
def view_dataset(dataset_id, con: DatasetController = None):
    pass


@core.route("/datasets/<dataset_id>/edit", methods=["POST", "GET"])
@require_permission("datasets.edit")
@injector.inject
def edit_dataset(dataset_id, con: DatasetController = None):
    pass


@core.route("/datasets/<dataset_id>/metadata", methods=["POST", "GET"])
@require_permission("datasets.edit")
@injector.inject
def edit_dataset_metadata(dataset_id, con: DatasetController = None):
    pass


@core.route("/datasets/<dataset_id>/publish", methods=["POST", "GET"])
@require_permission("datasets.publish")
@injector.inject
def publish_dataset(dataset_id, con: DatasetController = None):
    pass


@core.route("/datasets/<dataset_id>/<revision_no>")
@require_permission("datasets.view")
@injector.inject
def view_dataset_revision(dataset_id, revision_no, con: DatasetController = None):
    pass


@core.route("/datasets/<dataset_id>/<revision_no>/<profile_name>/<format_name>")
@require_permission("datasets.view")
@injector.inject
def generate_metadata_format(dataset_id, revision_no, profile_name, format_name):
    pass
