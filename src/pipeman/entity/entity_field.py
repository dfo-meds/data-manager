
from pipeman.entity.fields import ChoiceField, HtmlContentField
from pipeman.entity.controller import EntityController
from pipeman.entity.entity import FieldContainer
from autoinject import injector
import json
from pipeman.i18n import DelayedTranslationString, gettext, MultiLanguageString, MultiLanguageLink
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

    def choices(self):
        if self._value_cache is None:
            self._value_cache = self._load_values()
        return self._value_cache

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

    def _load_values(self):
        values = []
        if not ('repeatable' in self.field_config and self.field_config['repeatable']):
            values.append(("", DelayedTranslationString("pipeman.general.empty_select")))
        revisions = self.entity_revisions()
        old_rev_text = gettext("pipeman.general.outdated")
        dep_rev_text = gettext("pipeman.general.deprecated")
        loop_types = [self.field_config['entity_type']] if isinstance(self.field_config['entity_type'], str) else self.field_config['entity_type']
        for ent_type in loop_types:
            for entity, display, _ in self.ec.list_entities(ent_type):
                dep_text = f"{dep_rev_text}:" if entity.is_deprecated else ""
                latest_rev = entity.latest_revision()
                val_key = f"{entity.id}-{latest_rev.revision_no}"
                dn = json.loads(entity.display_names) if entity.display_names else {}
                if not entity.is_deprecated:
                    values.append((val_key, MultiLanguageString(dn)))
                for rev in revisions:
                    if rev[0] == entity.id and not rev[1] == latest_rev.revision_no:
                        specific_rev = entity.specific_revision(rev[1])
                        if specific_rev:
                            dep_val_key = f"{entity.id}-{specific_rev.revision_no}"
                            dn_dep = {
                                key: dn[key] + f" [{dep_text}{old_rev_text}:{specific_rev.revision_no}]"
                                for key in dn
                            }
                            values.append((dep_val_key, MultiLanguageString(dn_dep)))
                    elif rev[0] == entity.id and rev[1] == latest_rev.id and entity.is_deprecated:
                        dep_dn = {
                            key: f"{dn[key]} [{dep_text[:-1]}" for key in dn
                        }
                        values.append((val_key, MultiLanguageString(dep_dn)))
        return values if values else []

    def _process_value(self, val, **kwargs):
        if val is None or "-" not in val == '-' or val == "-":
            return None
        pieces = val.split("-", maxsplit=1)
        if not len(pieces) == 2:
            return None
        res = self.ec.load_entity(
            None,
            int(pieces[0]),
            int(pieces[1])
        )
        return res
