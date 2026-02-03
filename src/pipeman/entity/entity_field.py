from pipeman.entity.fields import ChoiceField, HtmlContentField, Keyword, Field
from pipeman.entity.controller import EntityController
from pipeman.entity.entity import FieldContainer
from pipeman.util.flask import EntitySelectField, DynamicFormField, TabbedFieldFormWidget
from autoinject import injector
from pipeman.i18n import gettext, MultiLanguageLink, MultiLanguageString
import typing as t
import flask
import markupsafe
import zrlog


class EntityRefMixin:

    def _extract_keywords(self):
        keywords = []
        keyword_display_field = self.config("keyword_config", "display_field", default=None)
        keyword_machine_field = self.config("keyword_config", "machine_name_field", default=None)
        for ent in self.data():
            if ent is not None:
                keywords.append(Keyword(
                    ent.container_id,
                    ent.data(keyword_machine_field) if keyword_machine_field else None,
                    ent.data(keyword_display_field) if keyword_display_field else ent.display_names(),
                    self.build_thesaurus(ent),
                    self.keyword_mode()
                ))
        return keywords

    def related_entities(self):
        data = self.data()
        if data is not None:
            if isinstance(data, FieldContainer):
                yield data
            else:
                for ent in data:
                    if ent:
                        yield ent


class ComponentReferenceField(EntityRefMixin, HtmlContentField):

    DATA_TYPE = "component_ref"

    ec: EntityController = None

    @injector.construct
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Component References are always repeatable
        self.field_config["repeatable"] = True

    def is_empty(self):
        for x, _, _ in self.component_list():
            if not x.is_deprecated:
                return False
        return True

    def display(self):
        return markupsafe.Markup(self._build_html_content())

    def data(self, **kwargs):
        _data = []
        for c, _, _ in self.component_list():
            if c.is_deprecated:
                continue
            ent = self.ec.load_entity(c.entity_type, c.id)
            if ent:
                _data.append(ent)
        return _data

    def _build_html_content(self):
        create_link = None
        if not self.parent_id:
            return gettext("pipeman.entity.message.add_components_after_creation")
        if self.parent_id and self.ec.has_access(self.field_config["entity_type"], "create"):
            # TODO: dataset access to edit??
            create_link = flask.url_for("core.create_component", obj_type=self.field_config["entity_type"], parent_id=self.parent_id, parent_type=self.parent_type)
        # TODO: improve this template to use tables and rows instead
        return flask.render_template(
            "component_ref.html",
            create_link=create_link,
            entities=self.component_list()
        )

    def component_list(self):
        if not self.parent_id:
            return
        return self.ec.list_components(self.field_config["entity_type"], self.parent_id, self.parent_type)

    def set_from_external(self, external_value, external_container_setter: callable):
        if not self.parent_id:
            raise ValueError("Parent object must be saved before a new entity can be added.")
        if isinstance(external_value, (list, tuple)):
            for obj in external_value:
                self.ec.create_or_update_entity(
                    obj,
                    external_container_setter,
                    self.field_config["entity_type"],
                    self.parent_id,
                    self.parent_type
                )
        else:
            self.ec.create_or_update_entity(
                external_value,
                external_container_setter,
                self.field_config["entity_type"],
                self.parent_id,
                self.parent_type
            )

    def _handle_raw(self, raw_value):
        raise NotImplementedError("ComponentReference field not implemented yet")


class InlineEntityReferenceField(EntityRefMixin, Field):

    DATA_TYPE = "inline_entity_ref"

    ec: EntityController = None

    @injector.construct
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # no bueno
        #self.field_config['repeatable'] = False
        self.field_config['multilingual'] = False

    def _control_class(self):
        return InlineEntityField

    def validators(self):
        return []

    def _update_from_keyword(self, keyword: str, keyword_dictionary: str) -> bool:
        return False

    def _extra_wtf_arguments(self) -> dict:
        args = {
            "entity_type": self.field_config["entity_type"],
            "original_data": self.value,
            'parent_is_repeatable': self.is_repeatable(),
            'allow_js_controls': self.allow_javascript_controls() and not self.is_repeatable()
        }
        return args

    def _format_for_ui(self, val):
        ent = self._process_value(val)
        if ent:
            code = '<table cellpadding="0" cellspacing="0" border="0" class="inline-entity-info property-list">'
            for display, value in ent.display_values():
                code += f'<tr><th>{display}</th><td>{value}</td></th></tr>'
            code += '</table>'
            return markupsafe.Markup(code)

    def _process_value(self, val, **kwargs):
        if val is None:
            return None
        return self.ec.reg.new_entity(
            self.field_config["entity_type"],
            parent_type="_field" if not self.is_repeatable() else "_field_repeatable",
            field_values=val
        )

    def set_from_external(self, external_value, external_container_setter: callable):
        if isinstance(external_value, (list, tuple)):
            if not self.is_repeatable():
                raise ValueError("List of items provided for non-repeatable field")
            for obj in external_value:
                self._handle_external_data(obj, external_container_setter)
        else:
            self._handle_external_data(external_value, external_container_setter)

    def _handle_external_data(self, obj: dict, setter: callable):
        pass

    def _handle_raw(self, raw_value):
        raise NotImplementedError("InlineEntityReference field not implemented yet")


class EntityReferenceField(EntityRefMixin, ChoiceField):

    DATA_TYPE = "entity_ref"

    ec: EntityController = None

    @injector.construct
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._value_cache = None

    def _control_class(self):
        return EntitySelectField

    def _update_from_keyword(self, keyword: str, keyword_dictionary: str) -> bool:
        return False

    def label(self) -> t.Union[str, MultiLanguageString]:
        return super().label()
        """""
        txt = self.field_config["label"] if "label" in self.field_config else ""
        link = flask.url_for("core.vocabulary_term_list", vocab_name=self.field_config["vocabulary_name"])
        if isinstance(txt, dict):
            return MultiLanguageLink(link, txt, new_tab=True)
        return MultiLanguageLink(link, {"und": txt}, new_tab=True)
        """

    def _extra_wtf_arguments(self) -> dict:
        args = {
            "entity_types": self.field_config["entity_type"],
            "allow_multiple": self.is_repeatable(),
            "allow_select2": self.allow_javascript_controls()
        }
        if "min_chars_to_search" in self.field_config and self.field_config["min_chars_to_search"]:
            args["min_chars_to_search"] = int(self.field_config["min_chars_to_search"])
        return args

    def _format_for_ui(self, val):
        entity = self._process_value(val)
        if entity is None:
            return ""
        return MultiLanguageLink(flask.url_for("core.view_entity", obj_type=entity.entity_type, obj_id=entity.container_id), entity.display_names())

    def _process_value(self, val, **kwargs):
        if val is None or val == '':
            return None
        try:
            ent_id, rev_no = EntitySelectField.parse_entity_option(val, False)
            return self.ec.load_entity(None, ent_id, rev_no)
        except ValueError:
            zrlog.get_logger("pipeman.entity_field").warning(f"Requested entity {val} does not exist")
            return None

    def sanitize_form_input(self, val):
        if self.is_repeatable() and isinstance(val, list) and len(val) == 1 and isinstance(val[0], list):
            return val[0]
        return val

    def set_from_external(self, external_value, external_container_setter: callable):
        if isinstance(external_value, (list, tuple)):
            if not self.is_repeatable():
                raise ValueError("Multiple entities specified for a non-repeatable field")
            existing = set(self.value) if self.value else set()
            for obj in external_value:
                ent = self.ec.create_or_update_entity(
                    obj,
                    external_container_setter,
                    self.field_config["entity_type"]
                )
                existing.add(ent.db_id)
            self.value = list(existing)
        else:
            ent = self.ec.create_or_update_entity(
                external_value,
                external_container_setter,
                self.field_config["entity_type"]
            )
            self.value = ent.db_id

    def _handle_raw(self, raw_value):
        raise NotImplementedError("EntityReference field not implemented yet")


class InlineEntityField(DynamicFormField):

    ec: EntityController = None

    @injector.construct
    def __init__(self, entity_type, original_data=None, parent_is_repeatable: bool = False, allow_js_controls: bool = True, **kwargs):
        self._blank_entity = self.ec.reg.new_entity(entity_type,
                                                    parent_type='_field' if not parent_is_repeatable else "_field_repeatable",
                                                    field_values=original_data or {})
        self.entity_type = entity_type
        if 'widget' not in kwargs:
            if allow_js_controls:
                kwargs['widget'] = TabbedFieldFormWidget()
        super().__init__(self._blank_entity.controls(), **kwargs)
