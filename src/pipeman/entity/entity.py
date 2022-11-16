from pipeman.entity.field_factory import FieldCreator
from autoinject import injector
from wtforms.form import BaseForm
import flask
from pipeman.i18n import gettext


class Entity:

    creator: FieldCreator = None

    @injector.construct
    def __init__(self, field_list: dict, field_values: dict = None):
        self._fields = {}
        self._load_fields(field_list, field_values)

    def _load_fields(self, field_list: dict, field_values: dict = None):
        for field_name, field_config in field_list:
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
        super().__init__(self.entity.controls(), *args, **kwargs)

    def handle_form(self):
        if flask.request.method == "POST":
            self.process(flask.request.form)
            if self.validate():
                self.entity.process_form_data(self.data)
                return True
            else:
                for key in self.errors:
                    for m in self.errors[key]:
                        flask.flash(gettext("pipeman.entity.form_error") % (self._fields[key].label.text, m), "error")
        return False
