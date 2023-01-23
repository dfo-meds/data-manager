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
from pipeman.util.flask import ConfirmationForm, paginate_query
import flask_login


@injector.injectable
class EntityController:

    db: Database = None
    reg: EntityRegistry = None

    @injector.construct
    def __init__(self, view_template="view_entity.html", edit_template="form.html"):
        self.view_template = view_template
        self.edit_template = edit_template

    def view_entity_page(self, ent):
        return flask.render_template(self.view_template, entity=ent)

    def edit_entity_form(self, ent):
        form = EntityForm(ent)
        if form.handle_form():
            self.save_entity(ent)
            return flask.redirect(flask.url_for("core.view_entity", obj_type=ent.entity_type, obj_id=ent.db_id))
        return flask.render_template(self.edit_template, form=form)

    def remove_entity_form(self, ent):
        form = ConfirmationForm()
        if form.validate_on_submit():
            self.remove_entity(ent)
            return flask.redirect(flask.url_for("core.list_entities_by_type", obj_type=ent.entity_type))
        return flask.render_template("form.html", form=form, instructions=gettext("pipeman.entity.remove_confirmation"))

    def restore_entity_form(self, ent):
        form = ConfirmationForm()
        if form.validate_on_submit():
            self.restore_entity(ent)
            return flask.redirect(flask.url_for("core.list_entities_by_type", obj_type=ent.entity_type))
        return flask.render_template("form.html", form=form, instructions=gettext("pipeman.entity.restore_confirmation"))

    def create_entity_form(self, entity_type):
        new_ent = self.reg.new_entity(entity_type)
        form = EntityForm(new_ent)
        if form.handle_form():
            self.save_entity(new_ent)
            return flask.redirect(flask.url_for("core.view_entity", obj_type=entity_type, obj_id=new_ent.db_id))
        return flask.render_template(self.edit_template, form=form)

    def has_access(self, entity_type, op):
        return entity_access(entity_type, op)

    def has_specific_access(self, entity, op):
        return specific_entity_access(entity)

    def _entity_iterator(self, query):
        for ent in query:
            dn = json.loads(ent.display_names) if ent.display_names else {}
            actions = [
                (flask.url_for("core.view_entity", obj_type=ent.entity_type, obj_id=ent.id), 'pipeman.general.view')
            ]
            yield ent, MultiLanguageString(dn), actions

    def list_entities(self, entity_type):
        with self.db as session:
            query = self._entity_query(entity_type, session)
            return self._entity_iterator(query)

    def _entity_query(self, entity_type, session):
        q = session.query(orm.Entity).filter_by(entity_type=entity_type)
        if not flask_login.current_user.has_permission("organization.manage_any"):
            q = q.filter(sa.or_(
                orm.Entity.organization_id.in_(flask_login.current_user.organizations),
                orm.Entity.organization_id == None
            ))
        return q.order_by(orm.Entity.id)

    def list_entities_page(self, entity_type):
        with self.db as session:
            query = self._entity_query(entity_type, session)
            query, page_args = paginate_query(query)
            create_link = ""
            if self.has_access(entity_type, "create"):
                create_link = flask.url_for("core.create_entity", obj_type=entity_type)
            return flask.render_template(
                "list_entities.html",
                entities=self._entity_iterator(query),
                create_link=create_link,
                **page_args
            )

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
            return self.reg.new_entity(
                entity_type,
                json.loads(entity_data.data) if entity_data else {},
                json.loads(e.display_names) if e.display_names else None,
                e.id,
                entity_data.id if entity_data else None,
                e.is_deprecated,
                e.organization_id
            )

    def save_entity(self, entity):
        with self.db as session:
            if entity.db_id is not None:
                e = session.query(orm.Entity).filter_by(entity_type=entity.entity_type, id=entity.db_id).first()
                e.modified_date = datetime.datetime.now()
                e.display_names = json.dumps(entity.get_displays())
                e.organization_id = entity.organization_id if entity.organization_id else None
            else:
                e = orm.Entity(
                    entity_type=entity.entity_type,
                    modified_date=datetime.datetime.now(),
                    created_date=datetime.datetime.now(),
                    display_names=json.dumps(entity.get_displays()),
                    organization_id=entity.organization_id if entity.organization_id else None
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

    @injector.construct
    def __init__(self, entity, *args, **kwargs):
        self.entity = entity
        cntrls = {
            "_name": TranslatableField(
                wtf.StringField,
                label=DelayedTranslationString("pipeman.entity_form.display_name"),
                default=self.entity.get_displays()
            ),
            "_org": wtf.SelectField(
                label=DelayedTranslationString("pipeman.entity.organization"),
                choices=self.ocontroller.list_organizations(),
                default=self.entity.organization_id if self.entity.organization_id else ""
            )
        }
        cntrls.update(self.entity.controls())
        cntrls["_submit"] = wtf.SubmitField(DelayedTranslationString("pipeman.entity_form.submit"))
        super().__init__(cntrls, *args, **kwargs)
        self.process()

    def handle_form(self):
        if flask.request.method == "POST":
            self.process(flask.request.form)
            if self.validate():
                d = self.data
                self.entity.process_form_data(d)
                for key in d["_name"]:
                    self.entity.set_display(key, d["_name"][key])
                self.entity.organization_id = d["_org"] if not d["_org"] == "" else None
                return True
            else:
                for key in self.errors:
                    for m in self.errors[key]:
                        flask.flash(gettext("pipeman.entity.form_error") % (self._fields[key].label.text, m), "error")
        return False
