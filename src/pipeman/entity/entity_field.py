
from pipeman.entity.fields import ChoiceField, HtmlContentField
from pipeman.entity.controller import EntityController
from pipeman.entity.entity import FieldContainer
from pipeman.util.flask import EntitySelectField
from autoinject import injector
from pipeman.i18n import gettext, MultiLanguageLink
import flask
import markupsafe


class EntityRefMixin:

    def extract_entity_keyword(self, value, language, default_thesaurus, extraction_method=None, thesaurus_field=None, **kwargs):
        field_name = self.field_config['keyword_config']['keyword_field'] if 'keyword_field' in self.field_config['keyword_config'] else None
        disp = value.display_names() if not field_name else value.data(field_name)
        thesaurus = default_thesaurus if not thesaurus_field else value.data(thesaurus_field)
        if isinstance(disp, dict):
            if language == "*":
                keys = [disp.keys()]
                omit_und = len(keys) > 1 or keys[0] != "und"
                keywords = []
                for key in disp:
                    if omit_und and key == "und":
                        continue
                    keywords.append((disp[key], key, thesaurus))
                return keywords
            elif language in disp:
                return [(disp[language], language, thesaurus), ]
            elif "und" in disp:
                return [(disp["und"], "und", thesaurus), ]
            else:
                return []
        else:
            return [(disp, "und", thesaurus), ]

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
        for c, _, _ in self._component_list():
            if c.is_deprecated:
                continue
            ent = self.ec.load_entity(c.entity_type, c.id)
            if ent:
                yield ent

    def _extract_keywords(self, language, default_thesaurus, **kwargs):
        keywords = set()
        for value in self.data():
            keywords.update(self.extract_entity_keyword(value, language, default_thesaurus, **kwargs))
        return keywords

    def _build_html_content(self):
        create_link = None
        if not self.parent_id:
            return gettext("pipeman.component.add_later")
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

    def _extra_wtf_arguments(self) -> dict:
        args = {
            "entity_types": self.field_config["entity_type"],
            "allow_multiple": self.is_repeatable()
        }
        if "min_chars_to_search" in self.field_config and self.field_config["min_chars_to_search"]:
            args["min_chars_to_search"] = int(self.field_config["min_chars_to_search"])
        return args

    def entity_revisions(self):
        refs = []
        if self.value and isinstance(self.value, list):
            for ref in self.value:
                if isinstance(ref, list):
                    print(ref)
                elif ref:
                    refs.append([int(x) for x in ref.split("-", maxsplit=1)])
        elif self.value:
            refs.append([int(x) for x in self.value.split("-", maxsplit=1)])
        return refs

    def _as_keyword(self, str_value, *args, **kwargs):
        value = self._process_value(str_value)
        return self.extract_entity_keyword(value, *args, **kwargs)

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
