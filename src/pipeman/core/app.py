import flask
import flask_login
from autoinject import injector
from pipeman.entity import EntityController, EntityRegistry
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


@core.route("/objects/<obj_type>/<obj_id>/edit")
@require_permission("entities.edit")
@injector.inject
def edit_entity(obj_type, obj_id, con: EntityController = None):
    if not con.reg.type_exists(obj_type):
        return flask.abort(404)
    if not con.has_access(obj_type, "edit"):
        return flask.abort(403)
    return con.edit_entity_form(obj_type, obj_id)
