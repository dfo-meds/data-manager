import flask
import flask_login
from autoinject import injector
from pipeman.entity import EntityController, EntityRegistry
from pipeman.dataset import DatasetController
from pipeman.auth import require_permission
from pipeman.util.errors import DatasetNotFoundError, EntityNotFoundError
from pipeman.workflow import WorkflowController
from pipeman.org import OrganizationController
from pipeman.files import FileController
from pipeman.metric import MetricController

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
    try:
        entity = con.load_entity(obj_type, obj_id)
        if not con.has_specific_access(entity, "view"):
            return flask.abort(403)
        return con.view_entity_page(entity)
    except EntityNotFoundError:
        return flask.abort(404)


@core.route("/objects/<obj_type>/<obj_id>/edit", methods=["POST", "GET"])
@require_permission("entities.edit")
@injector.inject
def edit_entity(obj_type, obj_id, con: EntityController = None):
    if not con.reg.type_exists(obj_type):
        return flask.abort(404)
    if not con.has_access(obj_type, "edit"):
        return flask.abort(403)
    try:
        entity = con.load_entity(obj_type, obj_id)
        if not con.has_specific_access(entity, "edit"):
            return flask.abort(403)
        return con.edit_entity_form(entity)
    except EntityNotFoundError:
        return flask.abort(404)


@core.route("/objects/<obj_type>/<obj_id>/remove", methods=["POST", "GET"])
@require_permission("entities.remove")
@injector.inject
def remove_entity(obj_type, obj_id, con: EntityController = None):
    if not con.reg.type_exists(obj_type):
        return flask.abort(404)
    if not con.has_access(obj_type, "remove"):
        return flask.abort(403)
    try:
        entity = con.load_entity(obj_type, obj_id)
        if not con.has_specific_access(entity, "remove"):
            return flask.abort(403)
        return con.remove_entity_form(entity)
    except EntityNotFoundError:
        return flask.abort(404)


@core.route("/objects/<obj_type>/<obj_id>/restore", methods=["POST", "GET"])
@require_permission("entities.restore")
@injector.inject
def restore_entity(obj_type, obj_id, con: EntityController = None):
    if not con.reg.type_exists(obj_type):
        return flask.abort(404)
    if not con.has_access(obj_type, "restore"):
        return flask.abort(403)
    try:
        entity = con.load_entity(obj_type, obj_id)
        if not con.has_specific_access(entity, "restore"):
            return flask.abort(403)
        return con.restore_entity_form(entity)
    except EntityNotFoundError:
        return flask.abort(404)


@core.route("/datasets")
@require_permission("datasets.view")
@injector.inject
def list_datasets(con: DatasetController = None):
    return con.list_datasets_page()


@core.route("/datasets/new", methods=["POST", "GET"])
@require_permission("datasets.create")
@injector.inject
def create_dataset(con: DatasetController = None):
    return con.create_dataset_form()


@core.route("/datasets/<dataset_id>")
@require_permission("datasets.view")
@injector.inject
def view_dataset(dataset_id, con: DatasetController = None):
    try:
        dataset = con.load_dataset(dataset_id)
        if not con.has_access(dataset, "view"):
            return flask.abort(403)
        return con.view_dataset_page(dataset)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.route("/datasets/<dataset_id>/edit", methods=["POST", "GET"])
@require_permission("datasets.edit")
@injector.inject
def edit_dataset(dataset_id, con: DatasetController = None):
    try:
        dataset = con.load_dataset(dataset_id)
        if not con.has_access(dataset, "edit"):
            return flask.abort(403)
        return con.edit_dataset_form(dataset)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.route("/datasets/<dataset_id>/metadata", methods=["POST", "GET"])
@require_permission("datasets.edit")
@injector.inject
def edit_dataset_metadata_base(dataset_id, con: DatasetController = None):
    try:
        dataset = con.load_dataset(dataset_id)
        if not con.has_access(dataset, "edit"):
            return flask.abort(403)
        return con.edit_metadata_form(dataset, None)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.route("/datasets/<dataset_id>/metadata/<display_group>", methods=["POST", "GET"])
@require_permission("datasets.edit")
@injector.inject
def edit_dataset_metadata(dataset_id, display_group, con: DatasetController = None):
    try:
        dataset = con.load_dataset(dataset_id)
        if not con.has_access(dataset, "edit"):
            return flask.abort(403)
        return con.edit_metadata_form(dataset, display_group)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.route("/datasets/<dataset_id>/activate", methods=["GET", "POST"])
@require_permission("datasets.activate")
@injector.inject
def activate_dataset(dataset_id, con: DatasetController = None):
    try:
        dataset = con.load_dataset(dataset_id)
        if not con.has_access(dataset, "activate"):
            return flask.abort(403)
        return con.activate_dataset_form(dataset)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.route("/datasets/<dataset_id>/publish", methods=["POST", "GET"])
@require_permission("datasets.publish")
@injector.inject
def publish_dataset(dataset_id, con: DatasetController = None):
    try:
        dataset = con.load_dataset(dataset_id)
        if not con.has_access(dataset, "publish"):
            return flask.abort(403)
        return con.publish_dataset_form(dataset)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.route("/datasets/<dataset_id>/remove", methods=["POST", "GET"])
@require_permission("datasets.remove")
@injector.inject
def remove_dataset(dataset_id, con: DatasetController = None):
    try:
        dataset = con.load_dataset(dataset_id)
        if not con.has_access(dataset, "remove"):
            return flask.abort(403)
        return con.remove_dataset_form(dataset)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.route("/datasets/<dataset_id>/restore", methods=["POST", "GET"])
@require_permission("datasets.restore")
@injector.inject
def restore_dataset(dataset_id, con: DatasetController = None):
    try:
        dataset = con.load_dataset(dataset_id)
        if not con.has_access(dataset, "restore"):
            return flask.abort(403)
        return con.restore_dataset_form(dataset)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.route("/datasets/<dataset_id>/<revision_no>")
@require_permission("datasets.view")
@injector.inject
def view_dataset_revision(dataset_id, revision_no, con: DatasetController = None):
    try:
        dataset = con.load_dataset(dataset_id, revision_no)
        if not con.has_access(dataset, "view"):
            return flask.abort(403)
        return con.view_revision_page(dataset)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.route("/datasets/<dataset_id>/<revision_no>/<profile_name>/<format_name>")
@require_permission("datasets.view")
@injector.inject
def generate_metadata_format(dataset_id, revision_no, profile_name, format_name, con: DatasetController = None):
    try:
        if not con.metadata_format_exists(profile_name, format_name):
            return flask.abort(404)
        dataset = con.load_dataset(dataset_id, revision_no)
        if not con.has_access(dataset, "view"):
            return flask.abort(403)
        return con.generate_metadata_file(dataset, profile_name, format_name)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.route("/action-items")
@require_permission("action_items.view")
@injector.inject
def list_workflow_items(wfc: WorkflowController = None):
    return wfc.list_workflow_items_page()


@core.route("/action-items/<item_id>")
@require_permission("action_items.view")
@injector.inject
def view_item(item_id, wfc: WorkflowController = None):
    return wfc.view_item_page(item_id)


@core.route("/action-items/<item_id>/approve", methods=["GET", "POST"])
@require_permission("action_items.decide")
@injector.inject
def approve_item(item_id, wfc: WorkflowController = None):
    return wfc.workflow_form(item_id, True)


@core.route("/action-items/<item_id>/cancel", methods=["GET", "POST"])
@require_permission("action_items.decide")
@injector.inject
def cancel_item(item_id, wfc: WorkflowController = None):
    return wfc.workflow_form(item_id, False)


@core.route("/api/pop-remote-item/<pipeline_name>")
@require_permission("remote_items.access")
@injector.inject
def pop_remote_item(pipeline_name, wfc: WorkflowController = None):
    return wfc.pop_remote_pipeline(pipeline_name)


@core.route("/api/release-remote-item/<item_id>")
@require_permission("remote_items.access")
@injector.inject
def release_remote_item(item_id, wfc: WorkflowController = None):
    return wfc.release_remote_lock(item_id)


@core.route("/api/renew-remote-item/<item_id>")
@require_permission("remote_items.access")
@injector.inject
def renew_remote_item(item_id, wfc: WorkflowController = None):
    return wfc.renew_remote_lock(item_id)


@core.route("/api/complete-remote-item/<item_id>")
@require_permission("remote_items.access")
@injector.inject
def item_completed(item_id, wfc: WorkflowController = None):
    return wfc.remote_work_complete(item_id, True)


@core.route("/api/cancel-remote-item/<item_id>")
@require_permission("remote_items.access")
@injector.inject
def item_cancelled(item_id, wfc: WorkflowController = None):
    return wfc.remote_work_complete(item_id, False)


@core.route("/organizations")
@require_permission("organizations.view")
@injector.inject
def list_organizations(oc: OrganizationController = None):
    return oc.list_organizations_page()


@core.route('/organizations/create', methods=['GET', 'POST'])
@require_permission("organizations.edit")
@injector.inject
def create_organization(oc: OrganizationController = None):
    return oc.create_organization_page()


@core.route("/organizations/<org_id>")
@require_permission("organizations.view")
@injector.inject
def view_organization(org_id, oc: OrganizationController = None):
    return oc.view_organization_page(org_id)


@core.route("/organizations/<org_id>/edit", methods=['GET', 'POST'])
@require_permission("organizations.edit")
@injector.inject
def edit_organization(org_id, oc: OrganizationController = None):
    return oc.edit_organization_form(org_id)


@core.route("/api/fire-event/<event_name>", methods=['POST'])
@require_permission("events.fire")
@injector.inject
def fire_event(event_name, wc: WorkflowController):
    if not wc.event_exists(event_name):
        return flask.abort(404)
    if not wc.has_access_to_event(event_name):
        return flask.abort(403)
    return wc.fire_event(event_name, flask.request.data)


@core.route("/events")
@require_permission("events.fire")
@injector.inject
def list_events(wc: WorkflowController = None):
    return wc.list_events_page()


@core.route("/events/<event_name>", methods=['GET', 'POST'])
@require_permission("events.fire")
@injector.inject
def event_firing_form(event_name, wc: WorkflowController):
    if not wc.event_exists(event_name):
        return flask.abort(404)
    if not wc.has_access_to_event(event_name):
        return flask.abort(403)
    return wc.event_form(event_name)


@core.route("/api/file-upload/<data_store_name>/<filename>", methods=['PUT'])
@require_permission("files.upload")
@injector.inject
def file_upload(data_store_name, filename, fc: FileController = None):
    if not fc.data_store_exists(data_store_name):
        return flask.abort(404)
    if not fc.has_access(data_store_name):
        return flask.abort(403)
    return fc.send_file_from_handle(data_store_name, filename, flask.request.stream)


@core.route("/api/file-upload-status/<item_id>")
@require_permission("files.upload")
@injector.inject
def file_upload_status(item_id, fc: FileController = None):
    return fc.upload_status(item_id)


@core.route("/api/metrics/<metric_name>/add")
@require_permission("metrics.add")
@injector.inject
def add_metric(metric_name, mc: MetricController = None):
    if not mc.can_add_metric(metric_name):
        return flask.abort(403)
    body = flask.request.json
    mc.add_metric(metric_name, body['value'], body['source_info'] if 'source_info' in body else '')
