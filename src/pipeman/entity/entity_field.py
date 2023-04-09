from pipeman.entity.fields import ChoiceField, HtmlContentField, Keyword
from pipeman.entity.controller import EntityController
from pipeman.entity.entity import FieldContainer
from pipeman.util.flask import EntitySelectField
from autoinject import injector
from pipeman.i18n import gettext, MultiLanguageLink, MultiLanguageString
import typing as t
import flask
import markupsafe


class EntityRefMixin:

    def _extract_keywords(self):
        keywords = []
        keyword_display_field = self.config("keyword_config", "display_field", default=None)
        keyword_machine_field = self.config("keyword_config", "machine_name_field", default=None)
        for ent in self.data():
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
        for x in self._component_list():
            return False
        return True

    def display(self):
        return markupsafe.Markup(self._build_html_content())

    def data(self, **kwargs):
        _data = []
        for c, _, _ in self._component_list():
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
        return flask.render_template(
            "component_ref.html",
            create_link=create_link,
            entities=self._component_list()
        )

    def _component_list(self):
        if not self.parent_id:
            return
        return self.ec.list_components(self.field_config["entity_type"], self.parent_id, self.parent_type)


class EntityReferenceField(EntityRefMixin, ChoiceField):

    DATA_TYPE = "entity_ref"

    ec: EntityController = None

    @injector.construct
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._value_cache = None

    def _control_class(self):
        return EntitySelectField

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
            "allow_multiple": self.is_repeatable()
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
        try:
            ent_id, rev_no = EntitySelectField.parse_entity_option(val, False)
            return self.ec.load_entity(None, ent_id, rev_no)
        except ValueError:
            return None

    def sanitize_form_input(self, val):
        if self.is_repeatable() and isinstance(val, list) and len(val) == 1 and isinstance(val[0], list):
            return val[0]
        return val
