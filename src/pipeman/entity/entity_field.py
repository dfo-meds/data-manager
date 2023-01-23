from pipeman.entity.fields import ChoiceField
from pipeman.entity.controller import EntityController
from autoinject import injector
import json
from pipeman.i18n import DelayedTranslationString, gettext, MultiLanguageString


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
                val_key = f"{entity.id}-{latest_rev.id}"
                dn = json.loads(entity.display_names) if entity.display_names else {}
                if not entity.is_deprecated:
                    values.append((val_key, MultiLanguageString(dn)))
                for rev in revisions:
                    if rev[0] == entity.id and not rev[1] == latest_rev.id:
                        specific_rev = entity.specific_revision(rev[1])
                        if specific_rev:
                            dep_val_key = f"{entity.id}-{specific_rev.id}"
                            dn_dep = {
                                key: dn[key] + f" [{dep_text}{old_rev_text}:{specific_rev.id}]"
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
        entity_id, rev_no = val.split("-", maxsplit=1)
        return self.ec.load_entity(
            None,
            int(entity_id),
            int(rev_no)
        )

