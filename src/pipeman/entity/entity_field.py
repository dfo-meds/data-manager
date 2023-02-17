
from pipeman.entity.fields import ChoiceField, HtmlContentField
from pipeman.entity.controller import EntityController
from autoinject import injector
import json
from pipeman.i18n import DelayedTranslationString, gettext, MultiLanguageString
import flask
import markupsafe


class ComponentReferenceField(HtmlContentField):

    DATA_TYPE = "component_ref"

    ec: EntityController = None

    @injector.construct
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def display(self):
        return markupsafe.Markup(self._build_html_content())

    def data(self, **kwargs):
        return [
            self.ec.load_entity(ent.entity_type, ent.id)
            for ent, name, actions in self._component_list()
        ]

    def get_keywords(self, language):
        if "is_keyword" not in self.field_config or not self.field_config["is_keyword"]:
            return set()
        keyword_mode = self.field_config["keyword_type"]
        keyword_field = self.field_config["keyword_field"] if "keyword_field" in self.field_config else None
        uri_field = self.field_config["keyword_uri_field"] if "keyword_uri_field" in self.field_config else None
        default_uri = self.field_config["keyword_uri"] if "keyword_uri" in self.field_config else None

        keywords = set()
        for ent in self._component_list():
            actual_ent = self.ec.load_entity(ent.entity_type, ent.id)
            uri = default_uri
            if uri_field:
                uri = actual_ent.data(uri_field)
            disp = actual_ent.data(keyword_field) if keyword_field else actual_ent.get_displays()
            if keyword_mode == "translated":
                if language == "*":
                    keywords.update({(v, uri) for v in disp.values()})
                if language in disp:
                    keywords.add(disp[language])
                elif "und" in disp:
                    keywords.add(disp["und"])
            elif keyword_mode == "all_languages":
                keywords.update(disp.values())
        return keywords

    def _build_html_content(self):
        create_link = None
        if self.ec.has_access(self.field_config["entity_type"], "create"):
            # TODO: dataset access to edit??
            create_link = flask.url_for("core.create_component", obj_type=self.field_config["entity_type"], dataset_id=self.parent_id)
        return flask.render_template(
            "component_ref.html",
            create_link=create_link,
            entities=self._component_list()
        )

    def _component_list(self):
        if not self.parent_id:
            return
        return self.ec.list_components(self.field_config["entity_type"], self.parent_id)


class EntityReferenceField(ChoiceField):

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

    def _get_display(self, value):
        keyword_field = self.field_config["keyword_field"] if "keyword_field" in self.field_config else None
        entity = self._process_value(value)
        if entity:
            return entity.data(keyword_field) if keyword_field else entity.get_displays()

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
                            key: dn[key] + f"[{dep_text[:-1]}" for key in dn
                        }
                        values.append((val_key, MultiLanguageString(dep_dn)))
        return values if values else []

    def _process_value(self, val, **kwargs):
        if val is None or "-" not in val:
            return None
        entity_id, rev_no = val.split("-", maxsplit=1)
        return self.ec.load_entity(
            None,
            int(entity_id),
            int(rev_no)
        )
