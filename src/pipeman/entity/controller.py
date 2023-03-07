from .entity import EntityRegistry
from autoinject import injector
import wtforms as wtf
from wtforms.form import BaseForm
import flask
from .entity import entity_access, specific_entity_access
from pipeman.i18n import gettext, MultiLanguageString, DelayedTranslationString
from pipeman.db import Database
from pipeman.util.flask import TranslatableField
import pipeman.db.orm as orm
from pipeman.util.errors import EntityNotFoundError
import json
import datetime
import sqlalchemy as sa
from pipeman.org import OrganizationController
from sqlalchemy.exc import IntegrityError
from pipeman.util.flask import ConfirmationForm, paginate_query, ActionList, Select2Widget
from pipeman.util.flask import ActionListColumn, DatabaseColumn, DataQuery, DataTable, DisplayNameColumn
import flask_login
import wtforms.validators as wtfv
import functools


@injector.injectable
class EntityController:

    db: Database = None
    reg: EntityRegistry = None

    @injector.construct
    def __init__(self, view_template="view_entity.html", edit_template="form.html"):
        self.view_template = view_template
        self.edit_template = edit_template

    def build_action_list(self, ent, short_list: bool = False):
        actions = ActionList()
        kwargs = {
            "obj_type": ent.entity_type,
            "obj_id": ent.db_id if hasattr(ent, "db_id") else ent.id
        }
        comp_kwargs = {
            "obj_type": ent.entity_type,
            "obj_id": ent.db_id if hasattr(ent, "db_id") else ent.id,
            "parent_id": ent.parent_id,
            "parent_type": ent.parent_type,
        }
        for_comp = ent.parent_id is not None
        if short_list:
            actions.add_action("pipeman.general.view", "core.view_entity", **kwargs)
        elif for_comp:
            if ent.parent_type == 'dataset':
                actions.add_action("pipeman.entity.view_dataset", "core.view_dataset", dataset_id=ent.parent_id)
        if self.has_specific_access(ent, "edit"):
            if for_comp:
                actions.add_action("pipeman.general.edit", "core.edit_component", **comp_kwargs)
            else:
                actions.add_action("pipeman.general.edit", "core.edit_entity", **kwargs)
        if self.has_specific_access(ent, "remove"):
            if for_comp:
                actions.add_action("pipeman.general.remove", "core.remove_component", **comp_kwargs)
            else:
                actions.add_action("pipeman.general.remove", "core.remove_entity", **kwargs)
        if self.has_specific_access(ent, "restore"):
            if for_comp:
                actions.add_action("pipeman.general.restore", "core.restore_component", **comp_kwargs)
            else:
                actions.add_action("pipeman.general.restore", "core.restore_entity", **kwargs)
        return actions

    def _build_format_list(self):
        pass

    def view_entity_page(self, ent):
        return flask.render_template(
            self.view_template,
            entity=ent,
            title=gettext("pipeman.entity_view.title"),
            actions=self.build_action_list(ent, False)
        )

    def create_component_form(self, entity_type, container):
        new_ent = self.reg.new_entity(entity_type, parent_id=container.container_id, parent_type=container.container_type)
        form = EntityForm(new_ent, container=container)
        if form.handle_form():
            self.save_entity(new_ent)
            flask.flash(gettext("pipeman.entity_create.success"), 'success')
            return flask.redirect(container.view_link())
        return flask.render_template(
            self.edit_template,
            form=form,
            title=gettext('pipeman.entity_create.title')
        )

    def edit_component_form(self, ent, container):
        form = EntityForm(ent, container=container)
        if form.handle_form():
            self.save_entity(ent)
            flask.flash(gettext("pipeman.entity_edit.success"), 'success')
            return flask.redirect(container.view_link())
        return flask.render_template(
            self.edit_template,
            form=form,
            title=gettext("pipeman.component_edit.title")
        )

    def remove_component_form(self, ent, container):
        form = ConfirmationForm()
        if form.validate_on_submit():
            self.remove_entity(ent)
            flask.flash(gettext("pipeman.entity_remove.success"), 'success')
            return flask.redirect(container.view_link())
        return flask.render_template(
            "form.html",
            form=form,
            instructions=gettext("pipeman.entity_remove.confirmation"),
            title=gettext("pipeman.entity_remove.title")
        )

    def restore_component_form(self, ent, container):
        form = ConfirmationForm()
        if form.validate_on_submit():
            self.restore_entity(ent)
            flask.flash(gettext("pipeman.entity_restore.success"), 'success')
            return flask.redirect(container.view_link())
        return flask.render_template(
            "form.html",
            form=form,
            instructions=gettext("pipeman.entity_restore.confirmation"),
            title=gettext("pipeman.entity_restore.title")
        )

    def edit_entity_form(self, ent):
        form = EntityForm(ent)
        if form.handle_form():
            self.save_entity(ent)
            flask.flash(gettext("pipeman.entity_edit.success"), 'success')
            return flask.redirect(flask.url_for("core.view_entity", obj_type=ent.entity_type, obj_id=ent.db_id))
        return flask.render_template(
            self.edit_template,
            form=form,
            title=gettext("pipeman.entity_edit.title")
        )

    def remove_entity_form(self, ent):
        form = ConfirmationForm()
        if form.validate_on_submit():
            self.remove_entity(ent)
            flask.flash(gettext("pipeman.entity_remove.success"), 'success')
            return flask.redirect(flask.url_for("core.list_entities_by_type", obj_type=ent.entity_type))
        return flask.render_template(
            "form.html",
            form=form,
            instructions=gettext("pipeman.entity_remove.confirmation"),
            title=gettext("pipeman.entity_remove.title")
        )

    def restore_entity_form(self, ent):
        form = ConfirmationForm()
        if form.validate_on_submit():
            self.restore_entity(ent)
            flask.flash(gettext("pipeman.entity_restore.success"), 'success')
            return flask.redirect(flask.url_for("core.list_entities_by_type", obj_type=ent.entity_type))
        return flask.render_template(
            "form.html",
            form=form,
            instructions=gettext("pipeman.entity_restore.confirmation"),
            title=gettext("pipeman.entity_restore.title")
        )

    def create_entity_form(self, entity_type):
        new_ent = self.reg.new_entity(entity_type)
        form = EntityForm(new_ent)
        if form.handle_form():
            self.save_entity(new_ent)
            flask.flash(gettext("pipeman.entity_create.success"), 'success')
            return flask.redirect(flask.url_for("core.view_entity", obj_type=entity_type, obj_id=new_ent.db_id))
        return flask.render_template(
            self.edit_template,
            form=form,
            title=gettext('pipeman.entity_create.title')
        )

    def has_access(self, entity_type, op):
        return entity_access(entity_type, op)

    def has_specific_access(self, entity, op):
        return specific_entity_access(entity, op)

    def _entity_iterator(self, query, short_list: bool = True):
        for ent in query:
            dn = json.loads(ent.display_names) if ent.display_names else {}
            actions = self.build_action_list(ent, short_list)
            yield ent, MultiLanguageString(dn), actions

    def list_entities(self, entity_type):
        with self.db as session:
            query = self._entity_query(entity_type, session)
            return self._entity_iterator(query)

    def list_components(self, entity_type, parent_id, parent_type):
        with self.db as session:
            query = self._entity_query(entity_type, session)
            query = query.filter_by(parent_id=parent_id, parent_type=parent_type)
            return self._entity_iterator(query, True)

    def _entity_query(self, entity_type, session):
        q = session.query(orm.Entity).filter_by(entity_type=entity_type)
        if not flask_login.current_user.has_permission("organization.manage_any"):
            q = q.filter(sa.or_(
                orm.Entity.organization_id.in_(flask_login.current_user.organizations),
                orm.Entity.organization_id == None
            ))
        return q.order_by(orm.Entity.id)

    def list_entities_page(self, entity_type):
        create_link = ""
        if self.has_access(entity_type, "create"):
            create_link = flask.url_for("core.create_entity", obj_type=entity_type)
        return flask.render_template(
            "list_entities.html",
            table=self._list_entities_table(entity_type),
            side_links=[
                (create_link, gettext("pipeman.create_entity.link"))
            ],
            title=gettext("pipeman.entity_list.title")
        )

    def list_entities_ajax(self, entity_type):
        table = self._list_entities_table(entity_type)
        return table.ajax_response()

    def _list_entities_table(self, entity_type):
        filters = []
        if not flask_login.current_user.has_permission("organization.manage_any"):
            filters.append(sa.or_(
                orm.Entity.organization_id.in_(flask_login.current_user.organizations),
                orm.Entity.organization_id == None
            ))
        dq = DataQuery(orm.Entity, entity_type=entity_type, extra_filters=filters)
        dt = DataTable(
            table_id="entity_list",
            base_query=dq,
            ajax_route=flask.url_for("core.list_entities_by_type_ajax", obj_type=entity_type),
            default_order=[("id", "asc")]
        )
        dt.add_column(DatabaseColumn("id", gettext("pipeman.entity.id"), allow_order=True))
        dt.add_column(DisplayNameColumn())
        dt.add_column(ActionListColumn(action_callback=functools.partial(self.build_action_list, short_list=True)))
        return dt

    def remove_entity(self, entity):
        with self.db as session:
            ent = session.query(orm.Entity).filter_by(entity_type=entity.entity_type, id=entity.db_id).first()
            ent.is_deprecated = True
            session.commit()

    def restore_entity(self, entity):
        with self.db as session:
            ent = session.query(orm.Entity).filter_by(entity_type=entity.entity_type, id=entity.db_id).first()
            ent.is_deprecated = False
            session.commit()

    def load_entity(self, entity_type, entity_id, revision_no=None):
        with self.db as session:
            if entity_type is None:
                e = session.query(orm.Entity).filter_by(id=entity_id).first()
                entity_type = e.entity_type if e else None
            else:
                e = session.query(orm.Entity).filter_by(entity_type=entity_type, id=entity_id).first()
            if not e:
                raise EntityNotFoundError(entity_id)
            entity_data = e.specific_revision(revision_no) if revision_no else e.latest_revision()
            x = self.reg.new_entity(
                entity_type,
                field_values=json.loads(entity_data.data) if entity_data else {},
                display_names=json.loads(e.display_names) if e.display_names else None,
                db_id=e.id,
                ed_id=entity_data.id if entity_data else None,
                is_deprecated=e.is_deprecated,
                org_id=e.organization_id,
                parent_id=e.parent_id,
                parent_type=e.parent_type
            )
            return x

    def save_entity(self, entity):
        with self.db as session:
            if entity.db_id is not None:
                e = session.query(orm.Entity).filter_by(entity_type=entity.entity_type, id=entity.db_id).first()
                e.modified_date = datetime.datetime.now()
                e.display_names = json.dumps(entity.display_names())
                e.organization_id = entity.organization_id if entity.organization_id else None
                e.parent_id = entity.parent_id if entity.parent_id else None
                e.parent_type = entity.parent_type if entity.parent_type else None
            else:
                e = orm.Entity(
                    entity_type=entity.entity_type,
                    modified_date=datetime.datetime.now(),
                    created_date=datetime.datetime.now(),
                    display_names=json.dumps(entity.display_names()),
                    organization_id=entity.organization_id if entity.organization_id else None,
                    parent_id=entity.parent_id,
                    parent_type=entity.parent_type
                )
                session.add(e)
            session.commit()
            entity.db_id = e.id
            retries = 5
            while retries > 0:
                retries -= 1
                try:
                    rev_nos = [ed.revision_no for ed in session.query(orm.EntityData).filter_by(entity_id=e.id)]
                    next_rev = 1 if not rev_nos else max(rev_nos) + 1
                    ed = orm.EntityData(
                        entity_id=e.id,
                        revision_no=next_rev,
                        data=json.dumps(entity.values()),
                        created_date=datetime.datetime.now()
                    )
                    session.add(ed)
                    session.commit()
                    break
                # Trap an error in case two people try to insert at the same time
                except IntegrityError:
                    continue


class EntityForm(BaseForm):

    ocontroller: OrganizationController = None
    dcontroller: "pipeman.dataset.controller.DatasetController" = None

    @injector.construct
    def __init__(self, entity, *args, container=None, **kwargs):
        self.entity = entity
        controls = {
            "_name": TranslatableField(
                wtf.StringField,
                label=DelayedTranslationString("pipeman.entity_form.display_name"),
                default=self.entity.display_names()
            ),
            "_org": wtf.SelectField(
                label=DelayedTranslationString("pipeman.entity.organization"),
                choices=self.ocontroller.list_organizations(),
                coerce=int,
                default=self.entity.organization_id if self.entity.organization_id else "",
                widget=Select2Widget(placeholder=DelayedTranslationString("pipeman.general.empty_select")),
                validators=[wtfv.InputRequired(message=DelayedTranslationString("pipeman.fields.required"))]
            ),
        }
        self.container = container
        if entity.is_component and container is None:
            controls["_dataset"] = wtf.SelectField(
                label=DelayedTranslationString("pipeman.entity.dataset"),
                choices=self.dcontroller.list_datasets_for_component(),
                default=self.entity.parent_id if self.entity.parent_id else "",
                widget=Select2Widget(placeholder=DelayedTranslationString("pipeman.general.empty_select")),
                validators=[wtfv.InputRequired(
                    message=DelayedTranslationString("pipeman.fields.required")
                )]
            )
        controls.update(self.entity.controls())
        controls["_submit"] = wtf.SubmitField(DelayedTranslationString("pipeman.general.submit"))
        super().__init__(controls, *args, **kwargs)
        self.process()

    def handle_form(self):
        if flask.request.method == "POST":
            self.process(flask.request.form)
            if self.validate():
                d = self.data
                self.entity.process_form_data(d)
                for key in d["_name"]:
                    self.entity.set_display_name(key, d["_name"][key])
                if self.container:
                    self.entity.parent_id = self.container.container_id
                    self.entity.parent_type = self.container.container_type
                elif self.entity.is_component and "_dataset" in d and d["_dataset"]:
                    self.entity.parent_id = d["_dataset"]
                    self.entity.parent_type = "dataset"
                self.entity.organization_id = d["_org"] if not d["_org"] == "" else None
                return True
            else:
                for key in self.errors:
                    for m in self.errors[key]:
                        flask.flash(gettext("pipeman.entity.form_error").format(
                            field=self._fields[key].label.text,
                            error=m
                        ), "error")
        return False

    def validate(self, extra_validators=None):
        """Validate the form by calling ``validate`` on each field.
        Returns ``True`` if validation passes.

        If the form defines a ``validate_<fieldname>`` method, it is
        appended as an extra validator for the field's ``validate``.

        :param extra_validators: A dict mapping field names to lists of
            extra validator methods to run. Extra validators run after
            validators passed when creating the field. If the form has
            ``validate_<fieldname>``, it is the last extra validator.
        """
        if extra_validators is not None:
            extra = extra_validators.copy()
        else:
            extra = {}

        for name in self._fields:
            inline = getattr(self.__class__, f"validate_{name}", None)
            if inline is not None:
                extra.setdefault(name, []).append(inline)

        return super().validate(extra)
