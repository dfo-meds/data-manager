from pipeman.entity.field_factory import FieldCreator
from autoinject import injector
import wtforms as wtf
from wtforms.form import BaseForm
import flask
import flask_login
from pipeman.i18n import gettext, MultiLanguageString, DelayedTranslationString
from pipeman.db import Database
import pipeman.db.orm as orm
from pipeman.util.errors import EntityNotFoundError
import json
import datetime
import copy
import math
from pipeman.util import deep_update
from pipeman.util.flask import TranslatableField


@injector.injectable_global
class EntityRegistry:

    def __init__(self):
        self._entity_types = {}

    def __iter__(self):
        return iter(self._entity_types)

    def type_exists(self, key):
        return key in self._entity_types

    def register_type(self, key, display_names, field_config):
        if key in self._entity_types:
            deep_update(self._entity_types[key]["display"], display_names)
            deep_update(self._entity_types[key]["fields"], field_config)
        else:
            self._entity_types[key] = {
                "display": display_names,
                "fields": field_config
            }

    def register_from_dict(self, cfg_dict):
        if cfg_dict:
            for key in cfg_dict:
                self.register_type(key, cfg_dict[key]["display"], cfg_dict[key]["fields"])

    def display(self, key):
        return MultiLanguageString(self._entity_types[key]["display"])

    def new_entity(self, key, values=None):
        return Entity(key, self._entity_types[key]["fields"], values)


@injector.injectable
class EntityController:

    db: Database = None
    reg: EntityRegistry = None

    @injector.construct
    def __init__(self, view_template="form.html", edit_template="form.html"):
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

    def create_entity_form(self, entity_type):
        new_ent = self.reg.new_entity(entity_type)
        form = EntityForm(new_ent)
        if form.handle_form():
            print(new_ent)
            self.save_entity(new_ent)
            return flask.redirect(flask.url_for("core.view_entity", obj_type=entity_type, obj_id=new_ent.db_id))
        return flask.render_template(self.edit_template, form=form)

    def has_access(self, entity_type, op):
        broad_perm = f"entities.{op}"
        specific_perm = f"entities.{op}.{entity_type}"
        if not flask_login.current_user.has_permission(broad_perm):
            return False
        if not flask_login.current_user.has_permission(specific_perm):
            return False
        return True

    def list_entities(self, entity_type, page=None, page_size=None):
        return EntityIterator(entity_type, page, page_size)

    def list_entities_page(self, entity_type):
        with self.db as session:
            page, page_size = self.get_pagination()
            count = session.query(orm.Entity.id).filter_by(entity_type=entity_type).count()
            create_link = ""
            if self.has_access(entity_type, "create"):
                create_link = flask.url_for("core.create_entity", obj_type=entity_type)
            return flask.render_template(
                "list_entities.html",
                entities=self.list_entities(entity_type, page, page_size),
                create_link=create_link,
                current_page=page,
                page_size=page_size,
                item_count=count,
                max_pages=math.ceil(count / page_size)
            )

    def get_pagination(self):
        page = flask.request.args.get("page", 1)
        page_size = flask.request.args.get("size", "")
        if not page_size.isdigit():
            page_size = 25
        else:
            page_size = int(page_size)
            if page_size > 250:
                page_size = 250
            elif page_size < 10:
                page_size = 10
        return page, page_size

    def load_entity(self, entity_type, entity_id):
        with self.db as session:
            e = session.query(orm.Entity).filter_by(entity_type=entity_type, id=entity_id).first()
            if not e:
                raise EntityNotFoundError(entity_id)
            return self.reg.new_entity(entity_type, json.loads(e.data))

    def save_entity(self, entity):
        with self.db as session:
            if entity.db_id is not None:
                e = session.query(orm.Entity).filter_by(entity_type=entity.entity_type, id=entity.db_id).first()
                e.data = json.dumps(entity.values())
                e.modified_date = datetime.datetime.now()
                e.display_names = json.dumps(entity.get_displays())
            else:
                e = orm.Entity(
                    entity_type=entity.entity_type,
                    data=json.dumps(entity.values()),
                    modified_date=datetime.datetime.now(),
                    created_date=datetime.datetime.now(),
                    display_names=json.dumps(entity.get_displays())
                )
                session.add(e)
            session.commit()
            entity.db_id = e.id


class EntityIterator:

    db: Database = None

    @injector.construct
    def __init__(self, entity_type, page=None, page_size=None):
        self.entity_type = entity_type
        self.page = page
        self.page_size = page_size

    def list_entities(self):
        with self.db as session:
            q = session.query(orm.Entity).filter_by(entity_type=self.entity_type).order_by(orm.Entity.id)
            if self.page_size is not None:
                q = q.limit(self.page_size).offset((self.page - 1)*self.page_size)
            for ent in q:
                yield ent


class Entity:

    creator: FieldCreator = None

    @injector.construct
    def __init__(self, entity_type, field_list: dict, field_values: dict = None, display_names: dict = None, db_id: int = None):
        self.entity_type = entity_type
        self._fields = {}
        self._display = {}
        self._load_fields(field_list, field_values)
        self.db_id = db_id

    def set_display(self, lang, name):
        self._display[lang] = name

    def get_display(self):
        return MultiLanguageString(self._display)

    def get_displays(self):
        return self._display

    def _load_fields(self, field_list: dict, field_values: dict = None):
        for field_name in field_list:
            field_config = copy.deepcopy(field_list[field_name])
            self._fields[field_name] = self.creator.build_field(field_name, field_config.pop('data_type'), field_config)
            if field_values and field_name in field_values:
                self._fields[field_name].value = field_values[field_name]

    def values(self) -> dict:
        return {fn: self._fields[fn].value for fn in self._fields}

    def controls(self):
        return {fn: self._fields[fn].control() for fn in self._fields}

    def process_form_data(self, form_data):
        for fn in self._fields:
            self._fields[fn].value = form_data[fn]


class EntityForm(BaseForm):

    def __init__(self, entity, *args, **kwargs):
        self.entity = entity
        cntrls = {
            "_name": TranslatableField(wtf.StringField, label=DelayedTranslationString("pipeman.entity_form.display_name"))
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
                return True
            else:
                for key in self.errors:
                    for m in self.errors[key]:
                        flask.flash(gettext("pipeman.entity.form_error") % (self._fields[key].label.text, m), "error")
        return False
