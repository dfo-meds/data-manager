import markupsafe
from autoinject import injector
from pipeman.db.db import Database, SessionWrapper
import pipeman.db.orm as orm
from pipeman.util.errors import DatasetNotFoundError, APIInputError
from .dataset import MetadataRegistry
import json
import datetime
from sqlalchemy.exc import IntegrityError
import flask_login
import flask
import sqlalchemy as sa
import wtforms as wtf
import zrlog
from pipeman.i18n import DelayedTranslationString, gettext, MultiLanguageString, format_datetime
from pipeman.util.flask import TranslatableField, ConfirmationForm, ActionList, Select2Widget, SecureBaseForm, \
    xml_escape, xml_quote_attr, c_escape
from pipeman.util.flask import DataQuery, DataTable, DatabaseColumn, ActionListColumn, DisplayNameColumn, HtmlField, flasht, PipemanFlaskForm
from pipeman.workflow import WorkflowController, WorkflowRegistry
from pipeman.core.util import user_list
from pipeman.org import OrganizationController
from pipeman.attachment import AttachmentController
from pipeman.dataset.dataset import Dataset
import wtforms.validators as wtfv
import functools
import re
import flask_wtf.file as fwf
import uuid
from pipeman.util.metrics import BlockTimer, time_function
import zirconium as zr

from pipeman.i18n.i18n import BaseTranslatableString


def is_empty(x):
    return x is None or x == '' or not x


@injector.injectable
class DatasetController:

    db: Database = None
    reg: MetadataRegistry = None
    workflow: WorkflowController = None
    acontroller: AttachmentController = None
    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self, view_template="view_dataset.html", edit_template="form.html", meta_edit_template="metadata_form.html"):
        self.view_template = view_template
        self.edit_template = edit_template
        self.meta_template = meta_edit_template
        self.log = zrlog.get_logger("pipeman.dataset")

    def metadata_format_exists(self, profile_name, format_name):
        return self.reg.metadata_format_exists(profile_name, format_name)

    def has_access(self, dataset, operation, is_attempt: bool = False):
        status = dataset.status if dataset.status is None or isinstance(dataset.status, str) else dataset.status()
        ds_id = dataset.id if hasattr(dataset, "id") else dataset.dataset_id
        if operation == "activate" and not (status == "DRAFT" and self.can_activate(dataset)):
            if is_attempt:
                self.log.warning(f"Access denied to activate non-draft dataset [{ds_id}]")
            return False
        if operation == "publish" and not (status == "ACTIVE" and self.can_publish(dataset)):
            if is_attempt:
                self.log.warning(f"Access denied to publish non-active dataset [{ds_id}]")
            return False
        if operation == "edit" and status == "UNDER_REVIEW":
            if is_attempt:
                self.log.warning(f"Access denied to edit dataset under review [{ds_id}]")
            return False
        if dataset.is_deprecated:
            if operation not in ("restore", "view"):
                if is_attempt:
                    self.log.warning(f"Access denied to {operation} deprecated dataset [{ds_id}], invalid operation")
                return False
            if not flask_login.current_user.has_permission(f"datasets.view.deprecated"):
                if is_attempt:
                    self.log.warning(f"Access denied to {operation} deprecated dataset [{ds_id}], missing permissions")
                return False
        elif operation == "restore":
            if is_attempt:
                self.log.warning(f"Access denied to restore non-deprecated dataset [{ds_id}]")
            return False
        if flask_login.current_user.has_permission(f"datasets.{operation}.all"):
            return True
        if flask_login.current_user.has_permission(f"datasets.{operation}.organization"):
            if self._has_organization_access(dataset, operation):
                return True
        if flask_login.current_user.has_permission(f"datasets.{operation}.assigned"):
            if flask_login.current_user.works_on(ds_id):
                return True
        if is_attempt:
            self.log.warning(f"Access denied  to {operation} dataset [{ds_id}], user missing access")
        return False

    def _has_organization_access(self, dataset, operation):
        if flask_login.current_user.has_permission("organizations.manage.any"):
            return True
        if not dataset.organization_id:
            return True
        if flask_login.current_user.belongs_to(dataset.organization_id):
            return True
        return False

    def list_datasets_page(self):
        with self.db as session:
            links = []
            if flask_login.current_user.has_permission("datasets.create"):
                links.append((
                    flask.url_for("core.create_dataset"),
                    gettext("pipeman.dataset.page.create_dataset.link")
                ))
            return flask.render_template(
                "data_table.html",
                table=self._list_datasets_table(),
                side_links=links,
                title=gettext('pipeman.dataset.page.list_datasets.title')
            )

    def list_datasets_ajax(self):
        return self._list_datasets_table().ajax_response()

    def _list_datasets_table(self):
        filters = self._base_filters()
        dq = DataQuery(orm.Dataset, extra_filters=filters)
        dt = DataTable(
            table_id="dataset_list",
            base_query=dq,
            ajax_route=flask.url_for("core.list_datasets_ajax"),
            default_order=[("id", "asc")]
        )
        dt.add_column(DatabaseColumn("id", gettext("pipeman.label.dataset.id"), allow_order=True))
        dt.add_column(DisplayNameColumn())
        dt.add_column(ActionListColumn(action_callback=functools.partial(self._build_action_list, short_list=True)))
        return dt

    def _build_action_list(self, ds, short_list: bool = True, for_revision: bool = False):
        actions = ActionList()
        kwargs = {
            "dataset_id": ds.dataset_id if hasattr(ds, "dataset_id") else ds.id
        }
        if short_list:
            actions.add_action("pipeman.dataset.page.view_dataset.link", "core.view_dataset", 0, **kwargs)
        if for_revision:
            actions.add_action("pipeman.dataset.page.view_current.link", "core.view_dataset", 0, **kwargs)
        else:
            actions.add_action("pipeman.dataset.page.validate_dataset.link", "core.validate_dataset", 40, **kwargs)
            if flask_login.current_user.has_permission("datasets.create"):
                actions.add_action("pipeman.dataset.page.copy_dataset.link", "core.copy_dataset", 50, **kwargs)
            if self.has_access(ds, 'edit'):
                actions.add_action("pipeman.dataset.page.edit_dataset.link", "core.edit_dataset", 1, **kwargs)
                actions.add_action("pipeman.dataset.page.edit_metadata.link", "core.edit_dataset_metadata_base", 2, **kwargs)
                if not short_list:
                    actions.add_action("pipeman.dataset.page.add_attachment.link", "core.add_attachment", 5, **kwargs)
            if self.has_access(ds, "remove"):
                actions.add_action("pipeman.dataset.page.remove_dataset.link", "core.remove_dataset", 99, **kwargs)
            if not short_list:
                if self.has_access(ds, 'activate'):
                    actions.add_action("pipeman.dataset.page.activate_dataset.link", "core.activate_dataset", 3, **kwargs)
                if self.has_access(ds, "publish"):
                    actions.add_action("pipeman.dataset.page.publish_dataset.link", "core.publish_dataset", 4, **kwargs)
                if self.has_access(ds, "restore"):
                    actions.add_action("pipeman.dataset.page.restore_dataset.link", "core.restore_dataset", 100, **kwargs)
        self.reg.extend_action_list(actions, ds, short_list, for_revision)
        return actions

    def _dataset_iterator(self, query):
        for ds in query:
            dsn = json.loads(ds.display_names) if ds.display_names else {}
            yield ds, MultiLanguageString(dsn), self._build_action_list(ds, True)

    def list_datasets_for_component(self):
        with self.db as session:
            ds_list = []
            query = self._dataset_query(session, "edit")
            for ds in query:
                dsn = json.loads(ds.display_names) if ds.display_names else {}
                ds_list.append((ds.id, MultiLanguageString(dsn)))
            return ds_list

    def _dataset_query(self, session, op="view"):
        q = session.query(orm.Dataset)
        for filter in self._base_filters(op):
            q = q.filter(filter)
        return q.order_by(orm.Dataset.id)

    def _base_filters(self, op="view"):
        if not flask_login.current_user.has_permission("datasets.view.deprecated"):
            yield orm.Dataset.is_deprecated == False
        if flask_login.current_user.has_permission(f"datasets.{op}.all"):
            pass
        elif flask_login.current_user.has_permission(f"datasets.{op}.organization") and flask_login.current_user.has_permission("organization.manage_any"):
            pass
        else:
            sql_ors = []
            if flask_login.current_user.has_permission(f"datasets.{op}.organization"):
                sql_ors.append(orm.Dataset.organization_id == None)
                if flask_login.current_user.organizations:
                    sql_ors.append(orm.Dataset.organization_id.in_(flask_login.current_user.organizations))
            if flask_login.current_user.has_permission(f"datasets.{op}.assigned") and flask_login.current_user.datasets:
                sql_ors.append(orm.Dataset.organization_id.in_(flask_login.current_user.datasets))
            if len(sql_ors) == 1:
                yield sql_ors[0]
            else:
                yield sa.or_(*sql_ors)

    def create_dataset_form(self):
        form = DatasetForm()
        if form.validate_on_submit():
            ds = form.build_dataset()
            self.save_dataset(ds)
            flasht("pipeman.dataset.page.create_dataset.success", "success")
            return flask.redirect(flask.url_for("core.view_dataset", dataset_id=ds.dataset_id))
        return flask.render_template(
            self.edit_template,
            form=form,
            title=gettext('pipeman.dataset.page.create_dataset.title')
        )

    def create_dataset_from_api_call(self):
        with self.db as session:
            builder = DatasetBuilder(session)
            dataset = builder.from_flask_api()
        self.save_dataset(dataset, True)
        response = {
            "dataset_id": dataset.dataset_id,
            'guid': dataset.guid(),
            "success": True,
        }
        return flask.jsonify(response)

    def view_dataset_page(self, dataset):
        groups = [x for x in self.reg.ordered_groups(dataset.supported_display_groups())]
        labels = {x: self.reg.display_group_label(x) for x in groups}
        with self.db as session:
            return flask.render_template(
                self.view_template,
                dataset=dataset,
                actions=self._build_action_list(dataset, False),
                title=dataset.label(),
                groups=groups,
                group_labels=labels,
                **self._build_extra_view_values(dataset, session)
            )

    def add_attachment_form(self, dataset):
        form = DatasetAttachmentForm()
        if form.validate_on_submit():
            if form.file_upload.data:
                aid = self.acontroller.create_attachment(
                    form.file_upload.data,
                    f"dataset{dataset.dataset_id}",
                    dataset.dataset_id,
                    form.file_name.data
                )
                if aid is not None:
                    flasht("pipeman.dataset.page.add_attachment.success", "success")
                else:
                    flasht("pipeman.dataset.page.add_attachment.error", "error")
                return flask.redirect(flask.url_for("core.view_dataset", dataset_id=dataset.dataset_id))
            else:
                flasht("pipeman.dataset.error.attachment_required", "error")
        return flask.render_template(
            "form.html",
            form=form,
            title=gettext("pipeman.dataset.page.add_attachment.title"),
            instructions=gettext("pipeman.dataset.page.add_attachment.instructions"),
            back=flask.url_for("core.view_dataset", dataset_id=dataset.dataset_id)
        )

    def _build_extra_view_values(self, dataset, session):
        ds = session.query(orm.Dataset).filter_by(id=dataset.container_id).first()
        return {
            "pubs": self._build_pub_list(ds),
            "atts": self._build_att_list(ds)
        }

    def _build_att_list(self, ds):
        for att in ds.attachments:
            link = flask.url_for("core.view_attachment", attachment_id=att.id)
            display = markupsafe.escape(f"{att.file_name} [{format_datetime(att.created_date)}]")
            yield link, display

    def _build_pub_list(self, ds):
        for rev in ds.data:
            if rev.is_published:
                link = flask.url_for("core.view_dataset_revision",
                                     dataset_id=rev.dataset_id,
                                     revision_no=rev.revision_no)
                app_link = None
                if rev.approval_item_id:
                    app_link = flask.url_for('core.view_item', item_id=rev.approval_item_id)
                yield link, rev.published_date, app_link

    def dataset_validation_page(self, dataset):
        return flask.render_template(
            "validation_page.html",
            dataset=dataset,
            actions=self._build_action_list(dataset, True),
            title=gettext("pipeman.dataset.page.validate_dataset.title"),
            errors=dataset.validate()
        )

    def copy_dataset_form(self, dataset):
        form = DatasetForm(dataset=dataset)
        if form.validate_on_submit():
            ds = form.build_dataset()
            self.save_dataset(ds, as_copy=True)
            flasht("pipeman.dataset.page.copy_dataset.success", "success")
            return flask.redirect(flask.url_for("core.view_dataset", dataset_id=ds.dataset_id))
        return flask.render_template(self.edit_template,
                                     form=form,
                                     title=gettext("pipeman.dataset.page.copy_dataset.title"))

    def edit_dataset_form(self, dataset):
        form = None
        if dataset.status() == "DRAFT" or self.has_access(dataset, "post_draft_full_edit"):
            form = DatasetForm(dataset=dataset)
        else:
            form = ApprovedDatasetForm(dataset=dataset)
        if form.validate_on_submit():
            ds = form.build_dataset()
            self.save_dataset(ds)
            flasht("pipeman.dataset.page.edit_dataset.success", "success")
            return flask.redirect(flask.url_for("core.view_dataset", dataset_id=ds.dataset_id))
        return flask.render_template(
            self.edit_template,
            form=form,
            title=gettext("pipeman.dataset.page.edit_dataset.title"),
            back=flask.url_for("core.view_dataset", dataset_id=dataset.dataset_id)
        )

    def edit_metadata_form(self, dataset, display_group):
        supported_groups = [x for x in self.reg.ordered_groups(dataset.supported_display_groups())]
        if supported_groups:
            if display_group is None:
                display_group = supported_groups[0]
            if not self.reg.display_group_exists(display_group):
                return flask.abort(404)
            if display_group not in supported_groups:
                return flask.abort(404)
        else:
            display_group = None
        form = DatasetMetadataForm(dataset, display_group)
        if form.handle_form():
            self.save_metadata(dataset)
            form = DatasetMetadataForm(dataset, display_group)
            flasht("pipeman.dataset.page.edit_metadata.success", "success")
        group_list = [
            (
                flask.url_for(
                    'core.edit_dataset_metadata',
                    dataset_id=dataset.dataset_id,
                    display_group=dg
                ),
                self.reg.display_group_label(dg)
            )
            for dg in supported_groups
        ]
        return flask.render_template(
            self.meta_template,
            form=form,
            title=gettext("pipeman.dataset.page.edit_metadata.title"),
            groups=group_list,
            back=flask.url_for("core.view_dataset", dataset_id=dataset.dataset_id)
        )

    def remove_dataset_form(self, dataset):
        form = ConfirmationForm()
        if form.validate_on_submit():
            self.remove_dataset(dataset)
            flasht("pipeman.dataset.page.remove_dataset.success", "success")
            return flask.redirect(flask.url_for("core.list_datasets"))
        return flask.render_template(
            "form.html",
            form=form,
            instructions=gettext("pipeman.dataset.page.remove_dataset.instructions"),
            title=gettext("pipeman.dataset.page.remove_dataset.title"),
            back=flask.url_for("core.view_dataset", dataset_id=dataset.dataset_id)
        )

    def restore_dataset_form(self, dataset):
        form = ConfirmationForm()
        if form.validate_on_submit():
            self.restore_dataset(dataset)
            flasht("pipeman.dataset.page.restore_dataset.success", "success")
            return flask.redirect(flask.url_for("core.list_datasets"))
        return flask.render_template(
            "form.html",
            form=form,
            instructions=gettext("pipeman.dataset.page.restore_dataset.instructions"),
            title=gettext("pipeman.dataset.page.restore_dataset.title"),
            back=flask.url_for("core.view_dataset", dataset_id=dataset.dataset_id)
        )

    def view_revision_page(self, dataset):
        groups = [x for x in self.reg.ordered_groups(dataset.supported_display_groups())]
        labels = {x: self.reg.display_group_label(x) for x in groups}
        return flask.render_template(
            self.view_template,
            dataset=dataset,
            for_revision=True,
            actions=self._build_action_list(dataset, False, True),
            title=f"{dataset.label()} v{dataset.revision_no}",
            groups=groups,
            group_labels=labels,
        )

    def publish_dataset_form(self, dataset):
        form = ConfirmationForm()
        dataset_url = flask.url_for("core.view_dataset", dataset_id=dataset.dataset_id)
        if form.validate_on_submit():
            self.publish_dataset(dataset)
            return flask.redirect(dataset_url)
        return flask.render_template(
            "form.html",
            form=form,
            instructions=gettext("pipeman.dataset.page.publish_dataset.instructions"),
            title=gettext("pipeman.dataset.page.publish_dataset.title"),
            back=dataset_url
        )

    def activate_dataset_form(self, dataset):
        form = ConfirmationForm()
        if form.validate_on_submit():
            self.activate_dataset(dataset)
            return flask.redirect(flask.url_for("core.view_dataset", dataset_id=dataset.dataset_id))
        return flask.render_template("form.html", form=form,
                                     instructions=gettext("pipeman.dataset.page.activate_dataset.instructions"),
                                     title=gettext("pipeman.dataset.page.activate_dataset.title"),
                                     back=flask.url_for("core.view_dataset", dataset_id=dataset.dataset_id))

    def can_activate(self, dataset):
        if hasattr(dataset, "dataset_id"):
            return not self.workflow.check_exists(
                "dataset_activation",
                dataset.extras["act_workflow"],
                object_id=dataset.dataset_id,
                object_type='dataset'
            )
        else:
            return not self.workflow.check_exists(
                "dataset_activation",
                dataset.act_workflow,
                object_id=dataset.id,
                object_type='dataset'
            )

    def activate_dataset(self, dataset):
        self.log.info(f"Activating dataset {dataset.dataset_id}")
        status, _ = self.workflow.start_workflow(
            "dataset_activation",
            dataset.extras['act_workflow'],
            {
                "dataset_id": dataset.dataset_id
            },
            dataset.dataset_id
        )
        if status == "COMPLETE":
            flasht("pipeman.dataset.message.activated", "success")
        elif status == "FAILURE":
            flasht("pipeman.dataset.error.during_activation", "error")
        else:
            flasht("pipeman.dataset.message.activation_in_progress", "success")

    def can_publish(self, dataset):
        if hasattr(dataset, "dataset_id"):
            return not self.workflow.check_exists(
                "dataset_publication",
                dataset.extras["pub_workflow"],
                object_id=dataset.dataset_id,
                object_type='dataset'
            )
        else:
            return not self.workflow.check_exists(
                "dataset_publication",
                dataset.pub_workflow,
                object_id=dataset.id,
                object_type='dataset'
            )

    def publish_dataset(self, dataset):
        self.log.info(f"Publishing dataset {dataset.dataset_id}")
        status, _ = self.workflow.start_workflow(
            "dataset_publication",
            dataset.extras['pub_workflow'],
            {
                "dataset_id": dataset.dataset_id,
                "metadata_id": dataset.metadata_id,
                "revision_no": dataset.revision_no
            },
            dataset.dataset_id
        )
        if status == "COMPLETE":
            flasht("pipeman.dataset.message.published", "success")
        elif status == "FAILURE":
            flasht("pipeman.dataset.error.during_publication", "error")
        else:
            flasht("pipeman.dataset.message.publication_in_progress", "success")

    def generate_metadata_content(self, dataset, profile_name, format_name, environment="live"):
        args = {
            "dataset": dataset,
            "environment": environment,
            "authority": self.config.as_str(("pipeman", "authority")),
            'xml_escape': xml_escape,
            'xml_quote': xml_quote_attr,
            'c_escape': c_escape,
            'is_empty': is_empty,
        }
        for processor in self.reg.metadata_processors(dataset.profiles, profile_name, format_name):
            updates = processor(**args)
            if updates:
                args.update(updates)
        mime_type, encoding, extension = self.reg.metadata_format_content_type(profile_name, format_name)
        content = flask.render_template(
            self.reg.metadata_format_template(profile_name, format_name),
            **args
        )
        content = re.sub("\n[ \t\n]{0,}\n", "\n", content.replace("\r\n", "\n")).strip("\r\n\t ")
        return content, mime_type, encoding, extension

    def generate_metadata_file(self, dataset, profile_name, format_name, environment="live"):
        content, mime_type, encoding, _ = self.generate_metadata_content(dataset, profile_name, format_name, environment)
        response = flask.Response(
            content,
            200,
            mimetype=mime_type
        )
        response.headers['Content-Type'] = f"{mime_type}; charset={encoding}"
        return response

    def remove_dataset(self, dataset):
        self.log.info(f"Removing dataset {dataset.dataset_id}")
        with self.db as session:
            ds = session.query(orm.Dataset).filter_by(id=dataset.dataset_id).first()
            ds.is_deprecated = True
            session.commit()

    def restore_dataset(self, dataset):
        self.log.info(f"Restoring dataset {dataset.dataset_id}")
        with self.db as session:
            ds = session.query(orm.Dataset).filter_by(id=dataset.dataset_id).first()
            ds.is_deprecated = False
            session.commit()

    def load_dataset(self, dataset_id, revision_no=None):
        self.log.debug(f"Loading dataset {dataset_id}-{revision_no if revision_no else '_latest_'}")
        with self.db as session:
            with BlockTimer("pipeman_dataset_load_dataset_object", "Time to load a dataset object"):
                ds = session.query(orm.Dataset).filter_by(id=dataset_id).first()
            if not ds:
                raise DatasetNotFoundError(dataset_id)
            with BlockTimer("pipeman_dataset_load_dataset_revision", "Time to load the revision of the dataset object"):
                if revision_no == "pub":
                    ds_data = ds.latest_published_revision()
                elif revision_no:
                    ds_data = ds.specific_revision(revision_no)
                else:
                    ds_data = ds.latest_revision()
            if revision_no and not ds_data:
                raise DatasetNotFoundError(f"{dataset_id}#{revision_no}")
            with BlockTimer("pipeman_dataset_load_dataset_build", "Time to build a dataset object itself"):
                return self.reg.build_dataset(
                    profiles=ds.profiles.replace("\r", "").split("\n"),
                    field_values=json.loads(ds_data.data) if ds_data else {},
                    dataset_id=ds.id,
                    ds_data_id=ds_data.id if ds_data else None,
                    revision_no=ds_data.revision_no if ds_data else None,
                    display_names=json.loads(ds.display_names) if ds.display_names else None,
                    is_deprecated=ds.is_deprecated,
                    org_id=ds.organization_id,
                    extras={
                        "pub_workflow": ds.pub_workflow,
                        "act_workflow": ds.act_workflow,
                        "status": ds.status,
                        "security_level": ds.security_level,
                        "created_date": ds.created_date,
                        "modified_date": ds.modified_date,
                        "guid": ds.guid,
                        "pub_date": ds_data.published_date if ds_data else None,
                        "metadata_modified_date": ds_data.modified_date if ds_data else ds.created_date,
                        "activated_item_id": ds.activated_item_id,
                        "approval_item_id": ds_data.approval_item_id if ds_data else None
                    },
                    users=[u.id for u in ds.users]
                )

    def save_dataset(self, dataset, force_new: bool = False):
        with self.db as session:
            ds = None
            name = "pipeman_dataset_save_dataset_update" if dataset.dataset_id else "pipeman_dataset_save_dataset_insert"
            desc = "Time to update an existing dataset" if dataset.dataset_id else "Time to insert an existing dataset"
            with BlockTimer(name, desc):
                if (not force_new) and dataset.dataset_id is not None:
                    ds = self._update_dataset(dataset, session)
                    self._update_user_access(dataset, ds, session)
                    session.commit()
                else:
                    ds = self._create_dataset(dataset, session)
                    # If creating a new dataset works but saving a copy of the metadata or user list doesn't,
                    # then having the dataset marked as deprecated prevents it from being used in an inconsistent
                    # state
                    if force_new:
                        ds.status = "DRAFT"
                        ds.is_deprecated = True
                    elif dataset.users:
                        ds.is_deprecated = True
                    session.commit()
                    dataset.dataset_id = ds.id
                    if dataset.users or force_new:
                        if dataset.users:
                            self._update_user_access(dataset, ds, session)
                        if force_new:
                            self._create_metadata(dataset, session, ds)
                        ds.is_deprecated = False
                        session.add(ds)
                        session.commit()

    def _update_user_access(self, dataset, ds, session):
        session.query(orm.user_dataset).filter(orm.user_dataset.c.dataset_id == ds.id).delete()
        for user_id in dataset.users:
            q = orm.user_dataset.insert().values({
                "user_id": user_id,
                "dataset_id": ds.id
            })
            session.execute(q)

    def _create_dataset(self, dataset: Dataset, session):
        ds = orm.Dataset(
            organization_id=int(dataset.organization_id) if dataset.organization_id else None,
            is_deprecated=dataset.is_deprecated,
            display_names=json.dumps(dataset.display_names()),
            profiles="\n".join(dataset.base_profiles),
            guid=str(uuid.uuid4()),
            created_by=flask_login.current_user.user_id
        )
        session.add(ds)
        dataset.extras['guid'] = ds.guid
        for keyword in dataset.extras:
            if keyword not in ('guid', 'created_date', 'modified_date',):
                setattr(ds, keyword, dataset.extras[keyword])
        return ds

    def _update_dataset(self, dataset: Dataset, session):
        ds = session.query(orm.Dataset).filter_by(id=dataset.dataset_id).first()
        if not ds:
            raise DatasetNotFoundError(dataset.dataset_id)
        ds.is_deprecated = dataset.is_deprecated
        ds.organization_id = int(dataset.organization_id) if dataset.organization_id is not None else None
        ds.display_names = json.dumps(dataset.display_names())
        ds.profiles = "\n".join(dataset.base_profiles)
        if not ds.guid:
            ds.guid = str(uuid.uuid4())
        for keyword in dataset.extras:
            if keyword not in ('guid', 'created_date', 'modified_date',):
                setattr(ds, keyword, dataset.extras[keyword])
        return ds


    @time_function("pipeman_dataset_save_metadata", "Time to save metadata to the database")
    def save_metadata(self, dataset):
        self.log.info(f"Saving metadata for dataset {dataset.dataset_id}")
        with self.db as session:
            if self._create_metadata(dataset, session):
                session.commit()

    def _create_metadata(self, dataset, session, ds = None):
        ds = ds if ds is not None else session.query(orm.Dataset).filter_by(id=dataset.dataset_id).first()
        retries = 5
        while retries > 0:
            retries -= 1
            try:
                self.log.debug(f"Attempting to save metadata")
                rev_nos = [dd.revision_no for dd in ds.data]
                next_rev = 1 if not rev_nos else max(rev_nos) + 1
                ds_data = orm.MetadataEdition(
                    dataset_id=ds.id,
                    revision_no=next_rev,
                    data=json.dumps(dataset.values()),
                    created_date=datetime.datetime.now(),
                    created_by=flask_login.current_user.user_id if flask_login.current_user else None
                )
                session.add(ds_data)
                return True
            except IntegrityError:
                self.log.exception(f"Error saving metadata, retries {retries}")
                continue
        return False


class DatasetBuilder:

    reg: MetadataRegistry = None
    wreg: WorkflowRegistry = None
    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self, db_session: SessionWrapper):
        self.session = db_session

    def from_flask_api(self) -> Dataset:
        """
        Structure:
        {
            profiles: [profile1, profile2, ...],
            org_name: "shortname",
        }
        """
        data = flask.request.get_json()
        kwargs = {}
        if not isinstance(data, dict):
            raise APIInputError("Dataset must be a JSON dictionary")
        profiles = self._get_profiles(data)
        kwargs = {
            "org_id": self._get_org_id(data),
            "display_names": self._get_display_names(data),
            "users": self._get_users(data),
            "is_deprecated": False,
            "extras": {
                "status": "DRAFT",
                "pub_workflow": self._get_publication_workflow(data),
                "act_workflow": self._get_activation_workflow(data),
                "security_level": self._get_security_level(data),
            },
        }
        metadata = self._get_metadata(data)
        dataset = self.reg.build_dataset(profiles, **kwargs)
        if metadata:
            dataset.set_from_file_metadata("json_api",metadata)
        return dataset

    def _get_metadata(self, data: dict):
        if 'metadata' in data and data['metadata']:
            if not isinstance(data['metadata'], dict):
                raise APIInputError("[metadata] must be a dictionary")
            return data['metadata']
        return None

    def _get_profiles(self, data: dict):
        if "profiles" not in data:
            raise APIInputError("Missing [profiles]")
        profiles = data["profiles"]
        if not isinstance(profiles, list):
            raise APIInputError("[profiles] must be a list")
        if not profiles:
            raise APIInputError("[profiles] must not be empty")
        for p in profiles:
            if not self.reg.profile_exists(p):
                raise APIInputError(f"Profile [{p}] does not exist")
        return profiles

    def _get_org_id(self, data):
        org_name = self.config.as_str("pipeman.dataset_api.defaults.organization_shortname", None)
        if "org_name" in data and data["org_name"]:
            org_name = data["org_name"]
        if org_name is None:
            return None
        org = self.session.query(orm.Organization).filter_by(short_name=org_name).first()
        if org:
            return org.id
        raise APIInputError(f"Invalid organization name [{data['org_name']}]")

    def _get_display_names(self, data):
        if "display_names" not in data or not data["display_names"]:
            raise APIInputError("[display_names] is mandatory")
        if isinstance(data["display_names"], str):
            return {"und": data["display_names"]}
        if isinstance(data["display_names"], dict):
            # todo: verify languages?
            return data["display_names"]
        raise APIInputError("[display_names] is an inappropriate input type")

    def _get_users(self, data):
        if "users" not in data or not data["users"]:
            return None
        ids = set()
        for u in data["users"]:
            u = self.session.query(orm.User).filter_by(username=u).first()
            if not u:
                raise APIInputError(f"Invalid username [{u}]")
            ids.add(u.id)
        return list(ids)

    def _get_activation_workflow(self, data):
        workflow_name = self.config.as_str("pipeman.dataset_api.defaults.activation_workflow", None)
        if 'activation_workflow' in data and data['activation_workflow']:
            workflow_name = data['activation_workflow']
        if workflow_name is None or not self.wreg.workflow_exists("dataset_activation", workflow_name):
            raise APIInputError(f"Invalid activation workflow [{workflow_name}]")
        return workflow_name

    def _get_publication_workflow(self, data):
        workflow_name = self.config.as_str("pipeman.dataset_api.defaults.publication_workflow", None)
        if 'publication_workflow' in data and data['publication_workflow']:
            workflow_name = data['publication_workflow']
        if workflow_name is None or not self.wreg.workflow_exists("dataset_publication", workflow_name):
            raise APIInputError(f"Invalid publication workflow [{workflow_name}]")
        return workflow_name

    def _get_security_level(self, data):
        level = self.config.as_str("pipeman.dataset_api.defaults.security_level", None)
        if 'security_level' in data and data['security_level']:
            level = data['security_level']
        if not self.reg.security_level_exists(level):
            raise APIInputError(f"Invalid security level [{level}]")
        return level


class DatasetForm(PipemanFlaskForm):

    reg: MetadataRegistry = None
    wreg: WorkflowRegistry = None
    ocontroller: OrganizationController = None

    names = TranslatableField(
        wtf.StringField,
        label=DelayedTranslationString("pipeman.common.display_name")
    )

    organization = wtf.SelectField(
        DelayedTranslationString("pipeman.label.dataset.organization"),
        choices=[],
        coerce=int,
        widget=Select2Widget(placeholder=DelayedTranslationString("pipeman.common.placeholder")),
        validators=[
            wtfv.InputRequired(
                message=DelayedTranslationString("pipeman.error.required_field")
            )
        ]
    )

    profiles = wtf.SelectMultipleField(
        DelayedTranslationString("pipeman.label.dataset.profiles"),
        choices=[],
        coerce=str,
        widget=Select2Widget(allow_multiple=True, placeholder=DelayedTranslationString("pipeman.common.placeholder"))
    )

    pub_workflow = wtf.SelectField(
        DelayedTranslationString("pipeman.label.dataset.publication_workflow"),
        choices=[],
        coerce=str,
        widget=Select2Widget(placeholder=DelayedTranslationString("pipeman.common.placeholder")),
        validators=[
            wtfv.InputRequired(
                message=DelayedTranslationString("pipeman.error.required_field")
            )
        ]
    )

    act_workflow = wtf.SelectField(
        DelayedTranslationString("pipeman.label.dataset.activation_workflow"),
        choices=[],
        coerce=str,
        widget=Select2Widget(placeholder=DelayedTranslationString("pipeman.common.placeholder")),
        validators=[
            wtfv.InputRequired(
                message=DelayedTranslationString("pipeman.error.required_field")
            )
        ]
    )

    assigned_users = wtf.SelectMultipleField(
        DelayedTranslationString("pipeman.label.dataset.assigned_users"),
        choices=[],
        coerce=int,
        widget=Select2Widget(allow_multiple=True, placeholder=DelayedTranslationString("pipeman.common.placeholder"))
    )

    security_level = wtf.SelectField(
        DelayedTranslationString("pipeman.label.dataset.security_level"),
        choices=[],
        coerce=str,
        widget=Select2Widget(placeholder=DelayedTranslationString("pipeman.common.placeholder")),
        validators=[
            wtfv.InputRequired(
                message=DelayedTranslationString("pipeman.error.required_field")
            )
        ]
    )

    submit = wtf.SubmitField(DelayedTranslationString("pipeman.common.submit"))

    @injector.construct
    def __init__(self, *args, dataset=None, **kwargs):
        self.dataset = None
        if dataset:
            self.dataset = dataset
            kwargs.update({
                "names": dataset.display_names(),
                "pub_workflow": dataset.extras['pub_workflow'],
                "act_workflow": dataset.extras['act_workflow'],
                "security_level": dataset.extras['security_level'],
                "profiles": dataset.base_profiles,
                "organization": dataset.organization_id,
                "assigned_users": dataset.users or []
            })
        super().__init__(*args, **kwargs)
        self.organization.choices = self.ocontroller.list_organizations()
        self.profiles.choices = self.reg.profiles_for_select()
        self.act_workflow.choices = [x for x in self.wreg.list_workflows("dataset_activation")]
        self.pub_workflow.choices = [x for x in self.wreg.list_workflows("dataset_publication")]
        self.security_level.choices = self.reg.security_labels_for_select()
        self.assigned_users.choices = user_list()

    def build_dataset(self):
        if self.dataset:
            for key in self.names.data:
                self.dataset.set_display_name(key, self.names.data[key])
            self.dataset.profiles = self.profiles.data
            self.dataset.extras = self.dataset.extras or {}
            self.dataset.extras["pub_workflow"] = self.pub_workflow.data
            self.dataset.extras["act_workflow"] = self.act_workflow.data
            self.dataset.extras["security_level"] = self.security_level.data
            self.dataset.users = self.assigned_users.data
            self.dataset.organization_id = self.organization.data
            return self.dataset
        else:
            return self.reg.build_dataset(
                profiles=self.profiles.data,
                display_names=self.names.data,
                org_id=self.organization.data,
                extras={
                    "pub_workflow": self.pub_workflow.data,
                    "act_workflow": self.act_workflow.data,
                    "security_level": self.security_level.data,
                    "status": "DRAFT",
                },
                users=self.assigned_users.data
            )


class DatasetAttachmentForm(PipemanFlaskForm):

    file_name = wtf.StringField(
        DelayedTranslationString("pipeman.label.attachment.file_name")
    )

    file_upload = fwf.FileField(
        DelayedTranslationString("pipeman.label.attachment.file"),
        validators=[
            fwf.FileAllowed(["pdf", "jpg", "png"])
        ]
    )

    submit = wtf.SubmitField(
        DelayedTranslationString("pipeman.common.submit")
    )


class ApprovedDatasetForm(PipemanFlaskForm):

    reg: MetadataRegistry = None

    names = TranslatableField(
        wtf.StringField,
        label=DelayedTranslationString("pipeman.common.display_name")
    )

    profiles = wtf.SelectMultipleField(
        DelayedTranslationString("pipeman.label.dataset.profiles"),
        choices=[],
        coerce=str,
        widget=Select2Widget(allow_multiple=True, placeholder=DelayedTranslationString("pipeman.common.placeholder"))
    )

    assigned_users = wtf.SelectMultipleField(
        DelayedTranslationString("pipeman.label.dataset.assigned_users"),
        choices=[],
        coerce=int
    )

    submit = wtf.SubmitField(DelayedTranslationString("pipeman.common.submit"))

    @injector.construct
    def __init__(self, *args, dataset=None, **kwargs):
        self.dataset = None
        if dataset:
            self.dataset = dataset
            kwargs["names"] = dataset.display_names()
            kwargs["profiles"] = dataset.base_profiles
            kwargs["assigned_users"] = dataset.users or []
        super().__init__(*args, **kwargs)
        self.assigned_users.choices = user_list()
        self.profiles.choices = self.reg.profiles_for_select()

    def build_dataset(self):
        for key in self.names.data:
            self.dataset.set_display_name(key, self.names.data[key])
        self.dataset.users = self.assigned_users.data
        self.dataset.profiles = self.profiles.data
        return self.dataset


class DatasetMetadataForm(SecureBaseForm):

    def __init__(self, entity, display_group, *args, **kwargs):
        self.entity = entity
        self.display_group = display_group
        cntrls = self.entity.controls(display_group)
        if not cntrls:
            cntrls["_no_fields"] = HtmlField(
                DelayedTranslationString("pipeman.dataset.message.no_fields"),
                label=""
            )
        cntrls["_submit"] = wtf.SubmitField(DelayedTranslationString("pipeman.common.submit"))
        super().__init__(cntrls, *args, **kwargs)
        self.process()

    def handle_form(self):
        if self.validate_on_submit():
            d = self.data
            self.entity.process_form_data(d, self.display_group)
            return True
        return False
