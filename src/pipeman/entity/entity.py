from pipeman.entity.field_factory import FieldCreator
from autoinject import injector
import flask
import flask_login
from pipeman.i18n import MultiLanguageString
import copy
from pipeman.util import deep_update
from functools import cache


def entity_access(entity_type: str, op: str) -> bool:
    broad_perm = f"entities.{op}"
    specific_perm = f"entities.{op}.{entity_type}"
    if not flask_login.current_user.has_permission(broad_perm):
        return False
    if not flask_login.current_user.has_permission(specific_perm):
        return False
    return True


def specific_entity_access(entity, op: str) -> bool:
    if op == "remove" and entity.is_deprecated:
        return False
    if op == "restore" and not entity.is_deprecated:
        return False
    if flask_login.current_user.has_permission("organization.manage_any"):
        return True
    return entity.organization_id in flask_login.current_user.organizations


@injector.injectable_global
class EntityRegistry:

    def __init__(self):
        self._entity_types = {}

    def __iter__(self):
        return iter(self._entity_types)

    def type_exists(self, key):
        return key in self._entity_types

    def register_type(self, key, display_names, field_config, validation, is_component: bool = None):
        if key in self._entity_types:
            deep_update(self._entity_types[key]["display"], display_names)
            deep_update(self._entity_types[key]["fields"], field_config)
            deep_update(self._entity_types[key]["validation"], validation)
            if is_component is not None:
                self._entity_types[key]['is_component'] = is_component
        else:
            self._entity_types[key] = {
                "display": display_names,
                "fields": field_config,
                "is_component": bool(is_component),
                "validation": validation
            }

    def register_from_dict(self, cfg_dict):
        if cfg_dict:
            for key in cfg_dict:
                self.register_type(
                    key,
                    cfg_dict[key]["display"] if "display" in cfg_dict[key] else {},
                    cfg_dict[key]["fields"] if "fields" in cfg_dict[key] else {},
                    cfg_dict[key]["validation"] if "validation" in cfg_dict[key] else {},
                    cfg_dict[key]["is_component"] if "is_component" in cfg_dict[key] else None
                )

    def display(self, key):
        return MultiLanguageString(self._entity_types[key]["display"])

    def new_entity(self, key, values=None, display_names=None, db_id=None, data_id=None, is_deprecated=False, org_id=None, dataset_id=None):
        return Entity(
            key,
            self._entity_types[key]["fields"],
            self._entity_types[key]["is_component"],
            values,
            display_names=display_names,
            db_id=db_id,
            ed_id=data_id,
            is_deprecated=is_deprecated,
            org_id=org_id,
            dataset_id=dataset_id
        )


class FieldContainer:

    creator: FieldCreator = None

    @injector.construct
    def __init__(self, container_id: int, field_list: dict, field_values: dict = None, display_names: dict = None, is_deprecated: bool = False, org_id: int = None):
        self._fields = {}
        self.container_id = container_id
        self.organization_id = org_id
        self._load_fields(field_list, field_values)
        self._display = display_names if display_names else {}
        self.is_deprecated = is_deprecated

    def _load_fields(self, field_list: dict, field_values: dict = None):
        for field_name in field_list:
            field_config = copy.deepcopy(field_list[field_name])
            self._fields[field_name] = self.creator.build_field(field_name, field_config.pop('data_type'), field_config, self.container_id)
            if field_values and field_name in field_values:
                self._fields[field_name].value = self._fields[field_name].unserialize(field_values[field_name])

    def display_values(self, display_group = None):
        for fn in self._ordered_field_names(display_group):
            if display_group is None or display_group == self._fields[fn].display_group:
                field = self._fields[fn]
                yield field.label(), field.display()

    def values(self) -> dict:
        return {
            fn: self._fields[fn].serialize(self._fields[fn].value)
            for fn in self._fields
        }

    def supports_display_group(self, display_group) -> bool:
        return any(self._fields[fn].display_group == display_group for fn in self._fields)

    def supported_display_groups(self) -> set:
        return set(self._fields[fn].display_group for fn in self._fields)

    def __html__(self):
        return str(self)

    @cache
    def data(self, key, **kwargs):
        if key in self._fields:
            try:
                return self._fields[key].data(**kwargs)
            except Exception as ex:
                print(ex)
                return "ERROR"

    def __contains__(self, item):
        return item in self._fields

    def __getitem__(self, key):
        if key not in self._fields:
            return ""
        return self.data(key)

    def controls(self, display_group=None):
        return {fn: self._fields[fn].control() for fn in self._ordered_field_names(display_group)}

    def _ordered_field_names(self, display_group=None):
        fields = [fn for fn in self._fields if display_group is None or display_group == self._fields[fn].display_group]
        fields.sort(key=lambda x: self._fields[x].order)
        return fields

    def process_form_data(self, form_data, display_group=None):
        for fn in self._fields:
            if display_group is None or display_group == self._fields[fn].display_group:
                self._fields[fn].value = self._fields[fn].cleanup_value(form_data[fn])

    def set_display(self, lang, name):
        self._display[lang] = name

    def get_display(self):
        return MultiLanguageString(self._display)

    def get_displays(self):
        return self._display


class Entity(FieldContainer):

    creator: FieldCreator = None

    @injector.construct
    def __init__(self, entity_type, field_list: dict, is_component: bool, field_values: dict = None, display_names: dict = None,
                 db_id: int = None, ed_id: int = None, is_deprecated: bool = False, org_id: int = None, dataset_id=None):
        super().__init__(db_id, field_list, field_values, display_names, is_deprecated, org_id)
        self.is_component = is_component
        self.entity_type = entity_type
        self.db_id = db_id
        self.entity_data_id = ed_id
        self.dataset_id=dataset_id

    def actions(self, for_view: bool = False):
        action_args = {
            "obj_type": self.entity_type,
            "obj_id": self.db_id
        }
        actions = []
        if not for_view:
            actions.append((flask.url_for("core.view_entity", **action_args), "pipeman.general.view"))
        if entity_access(self.entity_type, 'edit'):
            actions.append((
                flask.url_for("core.edit_entity", **action_args), "pipeman.general.edit"
            ))
        if (not self.is_deprecated) and entity_access(self.entity_type, 'remove'):
            actions.append((
                flask.url_for("core.remove_entity", **action_args), "pipeman.general.remove"
            ))
        if self.is_deprecated and entity_access(self.entity_type, 'restore'):
            actions.append((
                flask.url_for("core.restore_entity", **action_args), "pipeman.general.restore"
            ))
        return actions
