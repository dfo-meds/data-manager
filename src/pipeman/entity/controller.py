from .entity import EntityRegistry
from autoinject import injector
import wtforms as wtf
from wtforms.form import BaseForm
import flask
from .entity import entity_access
from pipeman.i18n import gettext, MultiLanguageString, DelayedTranslationString
from pipeman.db import Database
from pipeman.util.flask import TranslatableField
import pipeman.db.orm as orm
from pipeman.util.errors import EntityNotFoundError
import json
import datetime
import sqlalchemy as sa
import math
from sqlalchemy.exc import IntegrityError
from pipeman.util.flask import ConfirmationForm
import flask_login


@injector.injectable
class EntityController:

    db: Database = None
    reg: EntityRegistry = None

    @injector.construct
    def __init__(self, view_template="view_entity.html", edit_template="form.html"):
        self.view_template = view_template
        self.edit_template = edit_template

    def view_entity_page(self, entity_type, entity_id):
        ent = self.load_entity(entity_type, entity_id)
        return flask.render_template(self.view_template, entity=ent)

    def edit_entity_form(self, entity_type, entity_id):
        ent = self.load_entity(entity_type, entity_id)
        form = EntityForm(ent)
        if form.handle_form():
            self.save_entity(ent)
            return flask.redirect(flask.url_for("core.view_entity", obj_type=entity_type, obj_id=ent.db_id))
        return flask.render_template(self.edit_template, form=form)

    def remove_entity_form(self, entity_type, entity_id):
        ent = self.load_entity(entity_type, entity_id)
        form = ConfirmationForm()
        if form.validate_on_submit():
            self.remove_entity(ent)
            return flask.redirect(flask.url_for("core.list_entities_by_type", obj_type=entity_type))
        return flask.render_template("form.html", form=form, instructions=gettext("pipeman.entity.remove_confirmation"))

    def restore_entity_form(self, entity_type, entity_id):
        ent = self.load_entity(entity_type, entity_id)
        form = ConfirmationForm()
        if form.validate_on_submit():
            self.restore_entity(ent)
            return flask.redirect(flask.url_for("core.list_entities_by_type", obj_type=entity_type))
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

    def list_entities(self, entity_type, page=None, page_size=None):
        return EntityIterator(entity_type, page, page_size)

    def entity_references_page(self, entity_type, entity_id):
        pass

    def list_entities_page(self, entity_type):
        with self.db as session:
            count = session.query(orm.Entity.id).filter_by(entity_type=entity_type).count()
            page, page_size = self.get_pagination(count)
            max_pages = max(1,math.ceil(count / page_size))
            create_link = ""
            if self.has_access(entity_type, "create"):
                create_link = flask.url_for("core.create_entity", obj_type=entity_type)
            return flask.render_template(
                "list_entities.html",
                entities=self.list_entities(entity_type, page, page_size),
                create_link=create_link,
                current_page=page,
                page_size=page_size,
                page_count=max_pages,
                item_count=count,
            )

    def get_pagination(self, count):
        page_size = flask.request.args.get("size", "")
        if not page_size.isdigit():
            page_size = 25
        else:
            page_size = int(page_size)
            if page_size > 250:
                page_size = 250
            elif page_size < 10:
                page_size = 10
        page = flask.request.args.get("page", 1)
        if not page.isdigit():
            page = 1
        else:
            page = int(page)
            max_pages = math.ceil(count / page_size)
            if page > 1 and page > max_pages:
                page = max_pages
        return page, page_size

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


class EntityIterator:

    db: Database = None

    @injector.construct
    def __init__(self, entity_type, page=None, page_size=None):
        self.entity_type = entity_type
        self.page = page
        self.page_size = page_size

    def __iter__(self):
        generator = self.list_entities()
        return iter(generator)

    def list_entities(self):
        with self.db as session:
            q = session.query(orm.Entity).filter_by(entity_type=self.entity_type)
            if not flask_login.current_user.has_permission("organization.manage_any"):
                q = q.filter(sa.or_(
                    orm.Entity.organization_id.in_(flask_login.current_user.organizations),
                    orm.Entity.organization_id == None
                ))
            q = q.order_by(orm.Entity.id)
            if self.page_size is not None:
                q = q.limit(self.page_size).offset((self.page - 1)*self.page_size)
            for ent in q:
                dn = {}
                if ent.display_names:
                    dn = json.loads(ent.display_names)
                yield ent, MultiLanguageString(dn)


@injector.inject
def organization_list(db: Database = None):
    with db as session:
        all_access = flask_login.current_user.has_permission("organization.manage_any")
        global_access = flask_login.current_user.has_permission("organization.manage_global")
        orgs = []
        if global_access:
            orgs.append(("", DelayedTranslationString("pipeman.organization.global")))
        for org in session.query(orm.Organization):
            if all_access or flask_login.current_user.belongs_to(org.id):
                orgs.append((org.id, MultiLanguageString(json.loads(org.display_names))))
        return orgs


class EntityForm(BaseForm):

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
                choices=organization_list(),
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
                self.entity.organization_id = d["_org"]
                return True
            else:
                for key in self.errors:
                    for m in self.errors[key]:
                        flask.flash(gettext("pipeman.entity.form_error") % (self._fields[key].label.text, m), "error")
        return False
