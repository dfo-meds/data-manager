from autoinject import injector
from pipeman.db import Database
import pipeman.db.orm as orm
from pipeman.util.errors import DatasetNotFoundError
from .dataset import MetadataRegistry
import json
import datetime
from sqlalchemy.exc import IntegrityError
import flask_login
import flask
import sqlalchemy as sa
from wtforms.form import BaseForm
import wtforms as wtf
from flask_wtf import FlaskForm
from pipeman.i18n import DelayedTranslationString, gettext, MultiLanguageString
from pipeman.util.flask import TranslatableField, ConfirmationForm, paginate_query, ActionList
from pipeman.workflow import WorkflowController, WorkflowRegistry
from pipeman.core.util import user_list
from pipeman.org import OrganizationController
from xml.dom import minidom
import re
import uuid


@injector.injectable
class DatasetController:

    db: Database = None
    reg: MetadataRegistry = None
    workflow: WorkflowController = None

    @injector.construct
    def __init__(self, view_template="view_dataset.html", edit_template="form.html", meta_edit_template="metadata_form.html"):
        self.view_template = view_template
        self.edit_template = edit_template
        self.meta_template = meta_edit_template

    def metadata_format_exists(self, profile_name, format_name):
        return self.reg.metadata_format_exists(profile_name, format_name)

    def has_access(self, dataset, operation):
        status = dataset.status if dataset.status is None or isinstance(dataset.status, str) else dataset.status()
        if operation == "activate" and not status == "DRAFT":
            return False
        if operation == "publish" and not status == "ACTIVE":
            return False
        if operation == "edit" and status == "UNDER_REVIEW":
            return False
        if dataset.is_deprecated:
            if operation not in ("restore", "view"):
                return False
            if not flask_login.current_user.has_permission(f"datasets.deprecated_access"):
                return False
        elif operation == "restore":
            return False
        if flask_login.current_user.has_permission(f"datasets.{operation}.all"):
            return True
        if flask_login.current_user.has_permission(f"datasets.{operation}.organization"):
            return self._has_organization_access(dataset, operation)
        if flask_login.current_user.has_permission(f"datasets.{operation}.assigned"):
            return flask_login.current_user.works_on(dataset.id)
        return False

    def _has_organization_access(self, dataset, operation):
        if flask_login.current_user.has_permission("organization.manage_any"):
            return True
        if not dataset.organization_id:
            return True
        if flask_login.current_user.belongs_to(dataset.organization_id):
            return True
        return False

    def list_datasets_page(self):
        with self.db as session:
            query = self._dataset_query(session)
            query, page_args = paginate_query(query)
            create_link = ""
            if flask_login.current_user.has_permission("datasets.create"):
                create_link = flask.url_for("core.create_dataset")
            return flask.render_template(
                "list_datasets.html",
                datasets=self._dataset_iterator(query),
                create_link=create_link,
                title=gettext('pipeman.dataset_list.title'),
                **page_args
            )

    def _build_action_list(self, ds, short_list: bool = True):
        actions = ActionList()
        kwargs = {
            "dataset_id": ds.dataset_id if hasattr(ds, "dataset_id") else ds.id
        }
        if short_list:
            actions.add_action("pipeman.general.view", "core.view_dataset", **kwargs)
        if self.has_access(ds, 'edit'):
            actions.add_action("pipeman.general.edit", "core.edit_dataset", **kwargs)
            actions.add_action("pipeman.dataset_metadata.link", "core.edit_dataset_metadata_base", **kwargs)
        if not short_list:
            if self.has_access(ds, 'activate'):
                actions.add_action("pipeman.dataset_activate.link", "core.activate_dataset", **kwargs)
            if self.has_access(ds, "publish"):
                actions.add_action("pipeman.dataset_publish.link", "core.publish_dataset", **kwargs)
            if self.has_access(ds, "remove"):
                actions.add_action("pipeman.general.remove", "core.remove_dataset", **kwargs)
            if self.has_access(ds, "restore"):
                actions.add_action("pipeman.general.restore", "core.restore_dataset", **kwargs)
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
        if not flask_login.current_user.has_permission("datasets.deprecated_access"):
            q = q.filter_by(is_deprecated=False)
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
                q = q.filter(sql_ors[0])
            else:
                q = q.filter(sa.or_(*sql_ors))
        return q.order_by(orm.Dataset.id)

    def create_dataset_form(self):
        form = DatasetForm()
        if form.validate_on_submit():
            ds = form.build_dataset()
            self.save_dataset(ds)
            return flask.redirect(flask.url_for("core.view_dataset", dataset_id=ds.dataset_id))
        return flask.render_template(
            self.edit_template,
            form=form,
            title=gettext('pipeman.dataset_create.title')
        )

    def view_dataset_page(self, dataset):
        groups = [x for x in self.reg.ordered_groups(dataset.supported_display_groups())]
        labels = {x: self.reg.display_group_label(x) for x in groups}
        return flask.render_template(
            self.view_template,
            dataset=dataset,
            actions=self._build_action_list(dataset, False),
            title=dataset.get_display(),
            groups=groups,
            group_labels=labels
        )

    def edit_dataset_form(self, dataset):
        form = None
        if dataset.status() == "DRAFT" or self.has_access(dataset, "post_draft_full_edit"):
            form = DatasetForm(dataset=dataset)
        else:
            form = ApprovedDatasetForm(dataset=dataset)
        if form.validate_on_submit():
            ds = form.build_dataset()
            self.save_dataset(ds)
            return flask.redirect(flask.url_for("core.view_dataset", dataset_id=ds.dataset_id))
        return flask.render_template(
            self.edit_template,
            form=form,
            title=gettext("pipeman.dataset_edit.title"),
            back=flask.url_for("core.view_dataset", dataset_id=dataset.dataset_id)
        )

    def edit_metadata_form(self, dataset, display_group):
        supported_groups = [x for x in self.reg.ordered_groups(dataset.supported_display_groups())]
        if not supported_groups:
            return flask.abort(404)
        if display_group is None:
            display_group = supported_groups[0]
        if not self.reg.display_group_exists(display_group):
            return flask.abort(404)
        if display_group not in supported_groups:
            return flask.abort(404)
        form = DatasetMetadataForm(dataset, display_group)
        if form.handle_form():
            self.save_metadata(dataset)
            flask.flash(gettext("pipeman.dataset_metadata.success"), "success")
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
            title=gettext("pipeman.dataset_metadata.title"),
            groups=group_list,
            back=flask.url_for("core.view_dataset", dataset_id=dataset.dataset_id)
        )

    def remove_dataset_form(self, dataset):
        form = ConfirmationForm()
        if form.validate_on_submit():
            self.remove_dataset(dataset)
            return flask.redirect(flask.url_for("core.list_datasets"))
        return flask.render_template(
            "form.html",
            form=form,
            instructions=gettext("pipeman.dataset_remove.confirmation"),
            title=gettext("pipeman.dataset_remove.title"),
            back=flask.url_for("core.view_dataset", dataset_id=dataset.dataset_id)
        )

    def restore_dataset_form(self, dataset):
        form = ConfirmationForm()
        if form.validate_on_submit():
            self.restore_dataset(dataset)
            return flask.redirect(flask.url_for("core.list_datasets"))
        return flask.render_template(
            "form.html",
            form=form,
            instructions=gettext("pipeman.dataset_restore.confirmation"),
            title=gettext("pipeman.dataset_restore.title"),
            back=flask.url_for("core.view_dataset", dataset_id=dataset.dataset_id)
        )

    def view_revision_page(self, dataset):
        return flask.render_template(
            self.view_template,
            dataset=dataset,
            title=dataset.get_display(),
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
            instructions=gettext("pipeman.dataset_publish.confirmation"),
            title=gettext("pipeman.dataset_publish.title"),
            back=dataset_url
        )

    def activate_dataset_form(self, dataset):
        form = ConfirmationForm()
        if form.validate_on_submit():
            self.activate_dataset(dataset)
            return flask.redirect(flask.url_for("core.view_dataset", dataset_id=dataset.dataset_id))
        return flask.render_template("form.html", form=form,
                                     instructions=gettext("pipeman.dataset_activate.confirmation"),
                                     title=gettext("pipeman.dataset_activate.title"),
            back=flask.url_for("core.view_dataset", dataset_id=dataset.dataset_id))

    def activate_dataset(self, dataset):
        status, _ = self.workflow.start_workflow(
            "dataset_activation",
            dataset.extras['act_workflow'],
            {
                "dataset_id": dataset.dataset_id
            },
            dataset.dataset_id
        )
        if status == "COMPLETE":
            flask.flash(gettext("pipeman.dataset.activated"), "success")
        elif status == "FAILURE":
            flask.flash(gettext("pipeman.dataset.activation_error"), "error")
        else:
            flask.flash(gettext("pipeman.dataset.activation_in_progress"), "success")

    def publish_dataset(self, dataset):
        status, _ = self.workflow.start_workflow(
            "dataset_publication",
            dataset.extras['pub_workflow'],
            {
                "dataset_id": dataset.dataset_id,
                "metadata_id": dataset.metadata_id
            },
            dataset.dataset_id
        )
        if status == "COMPLETE":
            flask.flash(gettext("pipeman.dataset.published"), "success")
        elif status == "FAILURE":
            flask.flash(gettext("pipeman.dataset.publication_error"), "error")
        else:
            flask.flash(gettext("pipeman.dataset.publication_in_progress"), "success")

    def generate_metadata_file(self, dataset, profile_name, format_name):
        args = {
            "dataset": dataset
        }
        for processor in self.reg.metadata_processors(profile_name, format_name):
            updates = processor(**args)
            if updates:
                args.update(updates)
        content = flask.render_template(
            self.reg.metadata_format_template(profile_name, format_name),
            **args
        )
        return re.sub("\n[ \t\n]{0,}\n", "\n", content.replace("\r\n", "\n")).lstrip()

    def remove_dataset(self, dataset):
        with self.db as session:
            ds = session.query(orm.Dataset).filter_by(id=dataset.dataset_id).first()
            ds.is_deprecated = True
            session.commit()

    def restore_dataset(self, dataset):
        with self.db as session:
            ds = session.query(orm.Dataset).filter_by(id=dataset.dataset_id).first()
            ds.is_deprecated = False
            session.commit()

    def load_dataset(self, dataset_id, revision_no=None):
        with self.db as session:
            ds = session.query(orm.Dataset).filter_by(id=dataset_id).first()
            if not ds:
                raise DatasetNotFoundError(dataset_id)
            ds_data = ds.latest_revision() if revision_no is None else ds.specific_revision(revision_no)
            if revision_no and not ds_data:
                raise DatasetNotFoundError(f"{dataset_id}__{revision_no}")
            return self.reg.build_dataset(
                ds.profiles.replace("\r", "").split("\n"),
                json.loads(ds_data.data) if ds_data else {},
                ds.id,
                ds_data.id if ds_data else None,
                json.loads(ds.display_names) if ds.display_names else None,
                ds.is_deprecated,
                ds.organization_id,
                extras={
                    "pub_workflow": ds.pub_workflow,
                    "act_workflow": ds.act_workflow,
                    "status": ds.status,
                    "security_level": ds.security_level,
                    "created_date": ds.created_date,
                    "modified_date": ds.modified_date,
                    "guid": ds.guid
                }
            )

    def save_dataset(self, dataset):
        with self.db as session:
            ds = None
            if dataset.dataset_id:
                ds = session.query(orm.Dataset).filter_by(id=dataset.dataset_id).first()
                if not ds:
                    raise DatasetNotFoundError(dataset.dataset_id)
                ds.modified_date = datetime.datetime.now()
                ds.is_deprecated = dataset.is_deprecated
                ds.organization_id = dataset.organization_id
                ds.display_names = json.dumps(dataset.get_displays())
                ds.profiles = "\n".join(dataset.profiles)
                if not ds.guid:
                    ds.guid = str(uuid.uuid4())
            else:
                ds = orm.Dataset(
                    organization_id=dataset.organization_id,
                    created_date=datetime.datetime.now(),
                    modified_date=datetime.datetime.now(),
                    is_deprecated=dataset.is_deprecated,
                    display_names=json.dumps(dataset.get_displays()),
                    profiles="\n".join(dataset.profiles),
                    guid=str(uuid.uuid4())
                )
                session.add(ds)
            for keyword in dataset.extras:
                setattr(ds, keyword, dataset.extras[keyword])
            session.commit()
            dataset.dataset_id = ds.id
            session.query(orm.user_dataset).filter(orm.user_dataset.c.dataset_id == ds.id).delete()
            for user_id in dataset.users:
                q = orm.user_dataset.insert({
                    "user_id": user_id,
                    "dataset_id": ds.id
                })
                session.execute(q)
            session.commit()

    def save_metadata(self, dataset):
        with self.db as session:
            ds = session.query(orm.Dataset).filter_by(id=dataset.dataset_id).first()
            retries = 5
            while retries > 0:
                retries -= 1
                try:
                    rev_nos = [dd.revision_no for dd in ds.data]
                    next_rev = 1 if not rev_nos else max(rev_nos) + 1
                    ds_data = orm.MetadataEdition(
                        dataset_id=ds.id,
                        revision_no=next_rev,
                        data=json.dumps(dataset.values()),
                        created_date=datetime.datetime.now()
                    )
                    session.add(ds_data)
                    session.commit()
                    break
                except IntegrityError:
                    continue


class DatasetForm(FlaskForm):

    reg: MetadataRegistry = None
    wreg: WorkflowRegistry = None
    ocontroller: OrganizationController = None

    names = TranslatableField(
        wtf.StringField,
        label=DelayedTranslationString("pipeman.general.display_name")
    )

    organization = wtf.SelectField(
        DelayedTranslationString("pipeman.dataset.organization"),
        choices=[],
        coerce=int
    )

    profiles = wtf.SelectMultipleField(
        DelayedTranslationString("pipeman.dataset.profiles"),
        choices=[],
        coerce=str
    )

    pub_workflow = wtf.SelectField(
        DelayedTranslationString("pipeman.dataset.publication_workflow"),
        choices=[],
        coerce=str
    )

    act_workflow = wtf.SelectField(
        DelayedTranslationString("pipeman.dataset.activation_workflow"),
        choices=[],
        coerce=str
    )

    assigned_users = wtf.SelectMultipleField(
        DelayedTranslationString("pipeman.dataset.assigned_users"),
        choices=[],
        coerce=int
    )

    security_level = wtf.SelectField(
        DelayedTranslationString("pipeman.dataset.security_level"),
        choices=[],
        coerce=str
    )

    submit = wtf.SubmitField(DelayedTranslationString("pipeman.general.submit"))

    @injector.construct
    def __init__(self, *args, dataset=None, **kwargs):
        self.dataset = None
        if dataset:
            self.dataset = dataset
            kwargs.update({
                "names": dataset.get_displays(),
                "pub_workflow": dataset.extras['pub_workflow'],
                "act_workflow": dataset.extras['act_workflow'],
                "security_level": dataset.extras['security_level'],
                "profiles": dataset.profiles,
                "organization": dataset.organization_id,
            })
        super().__init__(*args, **kwargs)
        self.organization.choices = self.ocontroller.list_organizations()
        self.profiles.choices = self.reg.profiles_for_select()
        self.act_workflow.choices = self.wreg.list_workflows("dataset_activation")
        self.pub_workflow.choices = self.wreg.list_workflows("dataset_publication")
        self.security_level.choices = self.reg.security_labels_for_select()
        self.assigned_users.choices = user_list()

    def build_dataset(self):
        if self.dataset:
            for key in self.names.data:
                self.dataset.set_display(key, self.names.data[key])
            self.dataset.profiles = self.profiles.data
            self.dataset.extras["pub_workflow"] = self.pub_workflow.data
            self.dataset.extras["act_workflow"] = self.act_workflow.data
            self.dataset.extras["security_level"] = self.security_level.data
            self.dataset.users = self.assigned_users.data
            self.dataset.organization_id = self.organization.data
            return self.dataset
        else:
            return self.reg.build_dataset(
                self.profiles.data,
                None,
                None,
                None,
                self.names.data,
                False,
                self.organization.data,
                {
                    "pub_workflow": self.pub_workflow.data,
                    "act_workflow": self.act_workflow.data,
                    "security_level": self.security_level.data,
                    "status": "DRAFT",
                },
                self.assigned_users.data
            )


class ApprovedDatasetForm(FlaskForm):

    names = TranslatableField(
        wtf.StringField,
        label=DelayedTranslationString("pipeman.general.display_name")
    )

    assigned_users = wtf.SelectMultipleField(
        DelayedTranslationString("pipeman.dataset.assigned_users"),
        choices=[],
        coerce=int
    )

    submit = wtf.SubmitField(DelayedTranslationString("pipeman.general.submit"))

    def __init__(self, *args, dataset=None, **kwargs):
        self.dataset = None
        if dataset:
            self.dataset = dataset
            kwargs["names"] = dataset.get_displays()
        super().__init__(*args, **kwargs)
        self.assigned_users.choices = user_list()

    def build_dataset(self):
        for key in self.names.data:
            self.dataset.set_display(key, self.names.data[key])
        self.dataset.users = self.assigned_users.data
        return self.dataset


class DatasetMetadataForm(BaseForm):

    def __init__(self, entity, display_group, *args, **kwargs):
        self.entity = entity
        self.display_group = display_group
        cntrls = self.entity.controls(display_group)
        cntrls["_submit"] = wtf.SubmitField(DelayedTranslationString("pipeman.general.submit"))
        super().__init__(cntrls, *args, **kwargs)
        self.process()

    def handle_form(self):
        if flask.request.method == "POST":
            self.process(flask.request.form)
            if self.validate():
                d = self.data
                self.entity.process_form_data(d, self.display_group)
                return True
            else:
                for key in self.errors:
                    for m in self.errors[key]:
                        flask.flash(gettext("pipeman.entity.form_error") % (self._fields[key].label.text, m), "error")
        return False
