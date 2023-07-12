import flask
import flask_login
from autoinject import injector

from pipeman.attachment import AttachmentController
from pipeman.entity import EntityController, EntityRegistry
from pipeman.dataset import DatasetController
from pipeman.auth import require_permission
from pipeman.util.errors import DatasetNotFoundError, EntityNotFoundError
from pipeman.vocab import VocabularyTermController
from pipeman.workflow import WorkflowController
from pipeman.org import OrganizationController
from pipeman.files import FileController
from pipeman.i18n import gettext
from pipeman.util.flask import EntitySelectField, MultiLanguageBlueprint, CSPRegistry
import logging
import zrlog


base = flask.Blueprint("base", __name__)


# Main home page for logged in users (the welcome page)
@base.route("/h")
def home():
    return flask.render_template("welcome.html", title=gettext("pipeman.core.page.welcome.title"))


# The splash page welcomes new users
@base.route("/")
@injector.inject
def splash(cspr: CSPRegistry = None):
    cspr.set_static()
    return flask.render_template("splash.html")


@base.route("/-/health")
@injector.inject
def health_check(cspr: CSPRegistry = None):
    cspr.set_static()
    if flask.request.remote_addr != "127.0.0.1":
        return flask.abort(404)
    return "healthy", 200


core = MultiLanguageBlueprint("core", __name__)


@core.i18n_route("/objects")
@require_permission("entities.view")
@injector.inject
def list_entities(reg: EntityRegistry):
    entity_list = []
    show_all = flask_login.current_user.has_permission(f"entities.view.all")
    for k, _ in reg.list_entity_types(False):
        if show_all or flask_login.current_user.has_permission(f"entities.view.{k}"):
            entity_list.append((
                k,
                reg.display(k),
                flask.url_for("core.list_entities_by_type", obj_type=k),
                flask.url_for("core.create_entity", obj_type=k)
            ))
    entity_list.sort(key=lambda x: str(x[1]))
    return flask.render_template("list_entity_types.html", entity_types=entity_list, title=gettext('pipeman.entity.page.list_entity_types.title'))


@core.i18n_route("/objects/<obj_type>")
@require_permission("entities.view")
@injector.inject
def list_entities_by_type(obj_type, con: EntityController):
    if obj_type not in con.reg:
        zrlog.get_logger("pipeman.entity").warning(f"Entity type {obj_type[0:256]} requested but does not exist")
        return flask.abort(404)
    if not con.has_access(obj_type, "view"):
        return flask.abort(403)
    return con.list_entities_page(obj_type)


@core.route("/api/objects/<obj_type>", methods=["POST", "GET"])
@require_permission("entities.view")
@injector.inject
def list_entities_by_type_ajax(obj_type, con: EntityController):
    if obj_type not in con.reg:
        zrlog.get_logger("pipeman.entity").warning(f"Entity type {obj_type[0:256]} requested but does not exist")
        return flask.abort(404)
    if not con.has_access(obj_type, "view"):
        return flask.abort(403)
    return con.list_entities_ajax(obj_type)


@core.i18n_route("/objects/<obj_type>/new", methods=["POST", "GET"])
@require_permission("entities.create")
@injector.inject
def create_entity(obj_type, con: EntityController = None):
    if obj_type not in con.reg:
        zrlog.get_logger("pipeman.entity").warning(f"Entity type {obj_type[0:256]} requested but does not exist")
        return flask.abort(404)
    if not con.has_access(obj_type, "create", True):
        return flask.abort(403)
    return con.create_entity_form(obj_type)


def _get_container(parent_id, parent_type, dcon, econ):
    if parent_type == "dataset":
        try:
            ds = dcon.load_dataset(parent_id)
        except DatasetNotFoundError:
            return flask.abort(404)
        if not dcon.has_access(ds, "edit", True):
            return flask.abort(403)
        return ds
    elif parent_type == "entity":
        try:
            ent = econ.load_entity(None, parent_id)
        except EntityNotFoundError:
            return flask.abort(404)
        if not econ.has_specific_access(ent, "edit", True):
            return flask.abort(403)
        return ent
    else:
        return flask.abort(404)


@core.i18n_route("/objects/<obj_type>/new/<parent_type>/<int:parent_id>", methods=["POST", "GET"])
@require_permission("entities.create")
@require_permission("datasets.edit")
@injector.inject
def create_component(obj_type, parent_id, parent_type, dcon: DatasetController = None, econ: EntityController = None):
    if obj_type not in econ.reg:
        zrlog.get_logger("pipeman.entity").warning(f"Entity type {obj_type[0:256]} requested but does not exist")
        return flask.abort(404)
    if not econ.has_access(obj_type, "create", True):
        return flask.abort(403)
    container = _get_container(parent_id, parent_type, dcon, econ)
    return econ.create_component_form(obj_type, container)


@core.i18n_route("/objects/<obj_type>/<int:obj_id>/edit/<parent_type>/<int:parent_id>", methods=["POST", "GET"])
@require_permission("entities.edit")
@require_permission("datasets.edit")
@injector.inject
def edit_component(obj_type, obj_id, parent_id, parent_type, dcon: DatasetController = None, econ: EntityController = None):
    if obj_type not in econ.reg:
        zrlog.get_logger("pipeman.entity").warning(f"Entity type {obj_type[0:256]} requested but does not exist")
        return flask.abort(404)
    if not econ.has_access(obj_type, "edit", True):
        return flask.abort(403)
    entity = None
    try:
        entity = econ.load_entity(obj_type, obj_id)
    except EntityNotFoundError:
        return flask.abort(404)
    if not econ.has_specific_access(entity, "edit", True):
        return flask.abort(403)
    container = _get_container(parent_id, parent_type, dcon, econ)
    return econ.edit_component_form(entity, container)


@core.i18n_route("/objects/<obj_type>/<int:obj_id>/remove/<parent_type>/<int:parent_id>", methods=["POST", "GET"])
@require_permission("entities.remove")
@require_permission("datasets.edit")
@injector.inject
def remove_component(obj_type, obj_id, parent_id, parent_type, dcon: DatasetController = None, econ: EntityController = None):
    if obj_type not in econ.reg:
        zrlog.get_logger("pipeman.entity").warning(f"Entity type {obj_type[0:256]} requested but does not exist")
        return flask.abort(404)
    if not econ.has_access(obj_type, "remove", True):
        return flask.abort(403)
    entity = None
    try:
        entity = econ.load_entity(obj_type, obj_id)
    except EntityNotFoundError:
        return flask.abort(404)
    if not econ.has_specific_access(entity, "remove", True):
        return flask.abort(403)
    container = _get_container(parent_id, parent_type, dcon, econ)
    return econ.remove_component_form(entity, container)


@core.i18n_route("/objects/<obj_type>/<int:obj_id>/restore/<parent_type>/<int:parent_id>", methods=["POST", "GET"])
@require_permission("entities.restore")
@require_permission("datasets.edit")
@injector.inject
def restore_component(obj_type, obj_id, parent_id, parent_type, dcon: DatasetController = None, econ: EntityController = None):
    if obj_type not in econ.reg:
        zrlog.get_logger("pipeman.entity").warning(f"Entity type {obj_type[0:256]} requested but does not exist")
        return flask.abort(404)
    if not econ.has_access(obj_type, "restore", True):
        return flask.abort(403)
    entity = None
    try:
        entity = econ.load_entity(obj_type, obj_id)
    except EntityNotFoundError:
        return flask.abort(404)
    if not econ.has_specific_access(entity, "restore", True):
        return flask.abort(403)
    container = _get_container(parent_id, parent_type, dcon, econ)
    return econ.restore_component_form(entity, container)


@core.i18n_route("/objects/<obj_type>/<int:obj_id>")
@require_permission("entities.view")
@injector.inject
def view_entity(obj_type, obj_id, con: EntityController = None):
    if obj_type not in con.reg:
        zrlog.get_logger("pipeman.entity").warning(f"Entity type {obj_type[0:256]} requested but does not exist")
        return flask.abort(404)
    if not con.has_access(obj_type, "view", True):
        return flask.abort(403)
    try:
        entity = con.load_entity(obj_type, obj_id)
        if not con.has_specific_access(entity, "view", True):
            return flask.abort(403)
        return con.view_entity_page(entity)
    except EntityNotFoundError:
        return flask.abort(404)


@core.i18n_route("/objects/<obj_type>/<int:obj_id>/edit", methods=["POST", "GET"])
@require_permission("entities.edit")
@injector.inject
def edit_entity(obj_type, obj_id, con: EntityController = None):
    if obj_type not in con.reg:
        zrlog.get_logger("pipeman.entity").warning(f"Entity type {obj_type[0:256]} requested but does not exist")
        return flask.abort(404)
    if not con.has_access(obj_type, "edit", True):
        return flask.abort(403)
    try:
        entity = con.load_entity(obj_type, obj_id)
        if not con.has_specific_access(entity, "edit", True):
            return flask.abort(403)
        return con.edit_entity_form(entity)
    except EntityNotFoundError:
        return flask.abort(404)


@core.i18n_route("/objects/<obj_type>/<int:obj_id>/remove", methods=["POST", "GET"])
@require_permission("entities.remove")
@injector.inject
def remove_entity(obj_type, obj_id, con: EntityController = None):
    if obj_type not in con.reg:
        zrlog.get_logger("pipeman.entity").warning(f"Entity type {obj_type[0:256]} requested but does not exist")
        return flask.abort(404)
    if not con.has_access(obj_type, "remove", True):
        return flask.abort(403)
    try:
        entity = con.load_entity(obj_type, obj_id)
        if not con.has_specific_access(entity, "remove", True):
            return flask.abort(403)
        return con.remove_entity_form(entity)
    except EntityNotFoundError:
        return flask.abort(404)


@core.i18n_route("/objects/<obj_type>/<int:obj_id>/restore", methods=["POST", "GET"])
@require_permission("entities.restore")
@injector.inject
def restore_entity(obj_type, obj_id, con: EntityController = None):
    if obj_type not in con.reg:
        zrlog.get_logger("pipeman.entity").warning(f"Entity type {obj_type[0:256]} requested but does not exist")
        return flask.abort(404)
    if not con.has_access(obj_type, "restore", True):
        return flask.abort(403)
    try:
        entity = con.load_entity(obj_type, obj_id)
        if not con.has_specific_access(entity, "restore", True):
            return flask.abort(403)
        return con.restore_entity_form(entity)
    except EntityNotFoundError:
        return flask.abort(404)


@core.i18n_route("/datasets")
@require_permission("datasets.view")
@injector.inject
def list_datasets(con: DatasetController = None):
    return con.list_datasets_page()


@core.i18n_route("/api/datasets-ajax", methods=["POST", "GET"])
@require_permission("datasets.view")
@injector.inject
def list_datasets_ajax(con: DatasetController = None):
    return con.list_datasets_ajax()


@core.i18n_route("/datasets/new", methods=["POST", "GET"])
@require_permission("datasets.create")
@injector.inject
def create_dataset(con: DatasetController = None):
    return con.create_dataset_form()


@core.i18n_route("/attachment/<int:attachment_id>", methods=["GET"])
@require_permission("attachments.view")
@injector.inject
def view_attachment(attachment_id, atc: AttachmentController = None):
    return atc.download_attachment(attachment_id)


@core.i18n_route("/datasets/<int:dataset_id>")
@require_permission("datasets.view")
@injector.inject
def view_dataset(dataset_id, con: DatasetController = None):
    try:
        dataset = con.load_dataset(dataset_id)
        if not con.has_access(dataset, "view", is_attempt=True):
            return flask.abort(403)
        return con.view_dataset_page(dataset)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.i18n_route("/datasets/<int:dataset_id>/edit", methods=["POST", "GET"])
@require_permission("datasets.edit")
@injector.inject
def edit_dataset(dataset_id, con: DatasetController = None):
    try:
        dataset = con.load_dataset(dataset_id)
        if not con.has_access(dataset, "edit", is_attempt=True):
            return flask.abort(403)
        return con.edit_dataset_form(dataset)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.i18n_route("/datasets/<int:dataset_id>/copy", methods=["POST", "GET"])
@require_permission("datasets.create")
@injector.inject
def copy_dataset(dataset_id, con: DatasetController = None):
    try:
        dataset = con.load_dataset(dataset_id)
        if not con.has_access(dataset, "view", is_attempt=True):
            return flask.abort(403)
        return con.copy_dataset_form(dataset)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.i18n_route("/datasets/<int:dataset_id>/metadata", methods=["POST", "GET"])
@require_permission("datasets.edit")
@injector.inject
def edit_dataset_metadata_base(dataset_id, con: DatasetController = None):
    try:
        dataset = con.load_dataset(dataset_id)
        if not con.has_access(dataset, "edit", is_attempt=True):
            return flask.abort(403)
        return con.edit_metadata_form(dataset, None)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.i18n_route("/datasets/<int:dataset_id>/metadata/<display_group>", methods=["POST", "GET"])
@require_permission("datasets.edit")
@injector.inject
def edit_dataset_metadata(dataset_id, display_group, con: DatasetController = None):
    try:
        dataset = con.load_dataset(dataset_id)
        if not con.has_access(dataset, "edit", is_attempt=True):
            return flask.abort(403)
        return con.edit_metadata_form(dataset, display_group)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.i18n_route("/datasets/<int:dataset_id>/activate", methods=["GET", "POST"])
@require_permission("datasets.activate")
@injector.inject
def activate_dataset(dataset_id, con: DatasetController = None):
    try:
        dataset = con.load_dataset(dataset_id)
        if not con.has_access(dataset, "activate", is_attempt=True):
            return flask.abort(403)
        return con.activate_dataset_form(dataset)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.i18n_route("/datasets/<int:dataset_id>/attach", methods=["GET", "POST"])
@require_permission("datasets.edit")
@injector.inject
def add_attachment(dataset_id, con: DatasetController = None):
    try:
        dataset = con.load_dataset(dataset_id)
        if not con.has_access(dataset, "edit", is_attempt=True):
            return flask.abort(403)
        return con.add_attachment_form(dataset)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.i18n_route("/datasets/<int:dataset_id>/validate", methods=["GET"])
@require_permission("datasets.view")
@injector.inject
def validate_dataset(dataset_id, con: DatasetController = None):
    try:
        dataset = con.load_dataset(dataset_id)
        if not con.has_access(dataset, "view", is_attempt=True):
            return flask.abort(403)
        return con.dataset_validation_page(dataset)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.i18n_route("/datasets/<int:dataset_id>/publish", methods=["POST", "GET"])
@require_permission("datasets.publish")
@injector.inject
def publish_dataset(dataset_id, con: DatasetController = None):
    try:
        dataset = con.load_dataset(dataset_id)
        if not con.has_access(dataset, "publish", is_attempt=True):
            return flask.abort(403)
        return con.publish_dataset_form(dataset)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.i18n_route("/datasets/<int:dataset_id>/remove", methods=["POST", "GET"])
@require_permission("datasets.remove")
@injector.inject
def remove_dataset(dataset_id, con: DatasetController = None):
    try:
        dataset = con.load_dataset(dataset_id)
        if not con.has_access(dataset, "remove", is_attempt=True):
            return flask.abort(403)
        return con.remove_dataset_form(dataset)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.i18n_route("/datasets/<int:dataset_id>/restore", methods=["POST", "GET"])
@require_permission("datasets.restore")
@injector.inject
def restore_dataset(dataset_id, con: DatasetController = None):
    try:
        dataset = con.load_dataset(dataset_id)
        if not con.has_access(dataset, "restore", is_attempt=True):
            return flask.abort(403)
        return con.restore_dataset_form(dataset)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.i18n_route("/datasets/<int:dataset_id>/<int:revision_no>")
@require_permission("datasets.view")
@injector.inject
def view_dataset_revision(dataset_id, revision_no, con: DatasetController = None):
    try:
        dataset = con.load_dataset(dataset_id, revision_no)
        if not con.has_access(dataset, "view", is_attempt=True):
            return flask.abort(403)
        return con.view_revision_page(dataset)
    except DatasetNotFoundError:
        return flask.abort(404)


@core.i18n_route("/datasets/<int:dataset_id>/<int:revision_no>/<profile_name>/<format_name>")
@require_permission("datasets.view")
@injector.inject
def generate_metadata_format(dataset_id, revision_no, profile_name, format_name, con: DatasetController = None):
    return generate_metadata_format_long(dataset_id, revision_no, profile_name, format_name, "live")


@core.i18n_route("/datasets/<int:dataset_id>/<int:revision_no>/<profile_name>/<format_name>/<environment>")
@require_permission("datasets.view")
@injector.inject
def generate_metadata_format_long(dataset_id, revision_no, profile_name, format_name, environment, con: DatasetController = None):
    try:
        if not con.metadata_format_exists(profile_name, format_name):
            return flask.abort(404)
        dataset = con.load_dataset(dataset_id, revision_no)
        if not con.has_access(dataset, "view", is_attempt=True):
            return flask.abort(403)
        try:
            return con.generate_metadata_file(dataset, profile_name, format_name, environment)
        except Exception as ex:
            logging.getLogger("pipeman").exception(ex)
            flask.flash(str(gettext("pipeman.core.error.metadata_generation_error")), 'error')
            return flask.redirect(flask.url_for("core.view_dataset", dataset_id=dataset_id))
    except DatasetNotFoundError:
        return flask.abort(404)


@core.i18n_route("/api/datasets/<int:dataset_id>/<int:revision_no>/<profile_name>/<format_name>/<environment>")
@require_permission("datasets.view")
@injector.inject
def generate_metadata_format_api(dataset_id, revision_no, profile_name, format_name, environment, con: DatasetController = None):
    try:
        if not con.metadata_format_exists(profile_name, format_name):
            return flask.abort(404)
        dataset = con.load_dataset(dataset_id, revision_no)
        if not con.has_access(dataset, "view", is_attempt=True):
            return flask.abort(403)
        try:
            return con.generate_metadata_file(dataset, profile_name, format_name, environment)
        except Exception as ex:
            logging.getLogger("pipeman").exception(ex)
            return {'error': ''}, 500
    except DatasetNotFoundError:
        return flask.abort(404)


@core.i18n_route("/action-items")
@require_permission("action_items.view")
@injector.inject
def list_workflow_items(wfc: WorkflowController = None):
    return wfc.list_workflow_items_page(True)


@core.i18n_route("/action-history")
@require_permission("action_items.history")
@injector.inject
def list_workflow_history(wfc: WorkflowController = None):
    return wfc.list_workflow_items_page(False)


@core.route("/api/action-list/<int:active_only>", methods=["POST", "GET"])
@require_permission("action_items.view")
@injector.inject
def list_items_ajax(active_only: int, wfc: WorkflowController = None):
    active_only = int(active_only)
    if active_only not in (1, 0):
        return flask.abort(404)
    is_active_only = active_only == 1
    if is_active_only and not flask_login.current_user.has_permission("action_items.history"):
        raise flask.abort(403)
    return wfc.list_workflow_items_ajax(is_active_only)


@core.i18n_route("/action-items/<int:item_id>")
@require_permission("action_items.view")
@injector.inject
def view_item(item_id, wfc: WorkflowController = None):
    return wfc.view_item_page(item_id)


@core.i18n_route("/action-items/<int:item_id>/approve", methods=["GET", "POST"])
@require_permission("action_items.decide")
@injector.inject
def approve_item(item_id, wfc: WorkflowController = None):
    return wfc.workflow_form(item_id, True)


@core.i18n_route("/action-items/<int:item_id>/cancel", methods=["GET", "POST"])
@require_permission("action_items.decide")
@injector.inject
def cancel_item(item_id, wfc: WorkflowController = None):
    return wfc.workflow_form(item_id, False)


#@core.i18n_route("/action-items/<int:item_id>/retry", methods=["GET", "POST"])
#@require_permission("action_items.retry")
#@injector.inject
#def retry_item(item_id, wfc: WorkflowController = None):
#    return wfc.retry_form(item_id)


@core.i18n_route("/api/entity-select-field/<entity_types>/<int:by_revision>", methods=["POST", "GET"])
@require_permission("entities.view")
@injector.inject
def api_entity_select_field_list(entity_types, by_revision: int):
    by_revision = int(by_revision)
    if by_revision not in (0, 1):
        return flask.abort(404)
    return EntitySelectField.results_list(entity_types.split("|"), flask.request.args.get("term"), by_revision == 1)

"""""
@core.i18n_route("/api/pop-remote-item/<pipeline_name>")
@require_permission("remote_items.access")
@injector.inject
def pop_remote_item(pipeline_name, wfc: WorkflowController = None):
    return wfc.pop_remote_pipeline(pipeline_name)


@core.i18n_route("/api/release-remote-item/<int:item_id>")
@require_permission("remote_items.access")
@injector.inject
def release_remote_item(item_id, wfc: WorkflowController = None):
    return wfc.release_remote_lock(item_id)


@core.i18n_route("/api/renew-remote-item/<int:item_id>")
@require_permission("remote_items.access")
@injector.inject
def renew_remote_item(item_id, wfc: WorkflowController = None):
    return wfc.renew_remote_lock(item_id)


@core.i18n_route("/api/complete-remote-item/<int:item_id>")
@require_permission("remote_items.access")
@injector.inject
def item_completed(item_id, wfc: WorkflowController = None):
    return wfc.remote_work_complete(item_id, True)


@core.i18n_route("/api/cancel-remote-item/<int:item_id>")
@require_permission("remote_items.access")
@injector.inject
def item_cancelled(item_id, wfc: WorkflowController = None):
    return wfc.remote_work_complete(item_id, False)
"""

@core.i18n_route("/organizations")
@require_permission("organizations.view")
@injector.inject
def list_organizations(oc: OrganizationController = None):
    return oc.list_organizations_page()


@core.i18n_route('/organizations/create', methods=['GET', 'POST'])
@require_permission("organizations.create")
@injector.inject
def create_organization(oc: OrganizationController = None):
    return oc.create_organization_page()


@core.i18n_route("/organizations/<int:org_id>")
@require_permission("organizations.view")
@injector.inject
def view_organization(org_id, oc: OrganizationController = None):
    return oc.view_organization_page(org_id)


@core.i18n_route("/organizations/<int:org_id>/edit", methods=['GET', 'POST'])
@require_permission("organizations.edit")
@injector.inject
def edit_organization(org_id, oc: OrganizationController = None):
    return oc.edit_organization_form(org_id)

"""
@core.i18n_route("/api/fire-event/<event_name>", methods=['POST'])
@require_permission("events.fire")
@injector.inject
def fire_event(event_name, wc: WorkflowController):
    if not wc.event_exists(event_name):
        return flask.abort(404)
    if not wc.has_access_to_event(event_name):
        return flask.abort(403)
    return wc.fire_event(event_name, flask.request.data)


@core.i18n_route("/events")
@require_permission("events.fire")
@injector.inject
def list_events(wc: WorkflowController = None):
    return wc.list_events_page()


@core.i18n_route("/events/<event_name>", methods=['GET', 'POST'])
@require_permission("events.fire")
@injector.inject
def event_firing_form(event_name, wc: WorkflowController):
    if not wc.event_exists(event_name):
        return flask.abort(404)
    if not wc.has_access_to_event(event_name):
        return flask.abort(403)
    return wc.event_form(event_name)

"""


@core.i18n_route("/api/file-upload/<data_store_name>/<filename>", methods=['PUT'])
@require_permission("files.upload")
@injector.inject
def file_upload(data_store_name, filename, fc: FileController = None):
    if not fc.data_store_exists(data_store_name):
        return flask.abort(404)
    if not fc.has_access(data_store_name):
        return flask.abort(403)
    return fc.send_file_from_handle(data_store_name, filename, flask.request.data)


@core.i18n_route("/api/file-upload-status/<int:item_id>")
@require_permission("files.upload")
@injector.inject
def file_upload_status(item_id, fc: FileController = None):
    return fc.upload_status(item_id)


@core.i18n_route("/vocabulary")
@require_permission("vocabularies.view")
@injector.inject
def list_vocabularies(vtc: VocabularyTermController = None):
    return vtc.list_vocabularies_page()


@core.i18n_route("/vocabulary/<vocab_name>")
@require_permission("vocabularies.view")
@injector.inject
def vocabulary_term_list(vocab_name, vtc: VocabularyTermController = None):
    if vocab_name not in vtc.reg:
        return flask.abort(404)
    return vtc.list_terms_page(vocab_name)
