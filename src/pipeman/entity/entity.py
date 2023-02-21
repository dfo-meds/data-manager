from pipeman.entity.field_factory import FieldCreator
from pipeman.entity.fields import Field
from autoinject import injector
import flask
import flask_login
from pipeman.i18n import MultiLanguageString
import copy
from pipeman.util import deep_update, load_object
from functools import cache
import markupsafe
from pipeman.i18n import gettext


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
        ent = Entity(
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
        validation = self._entity_types[key]['validation'] or {}
        if 'required' in validation and validation['required']:
            for fn in validation['required']:
                ent.add_field_validator(fn, RequiredFieldValidator())
        if 'recommended' in validation and validation['recommended']:
            for fn in validation['recommended']:
                ent.add_field_validator(fn, RecommendedFieldValidator())
        if 'custom' in validation and validation['custom']:
            for call in validation['custom']:
                ent.add_self_validator(CustomValidator(call))
        return ent


class FieldContainer:

    creator: FieldCreator = None

    @injector.construct
    def __init__(self, container_type: str, container_id: int, field_list: dict, field_values: dict = None, display_names: dict = None, is_deprecated: bool = False, org_id: int = None):
        self._fields = {}
        self.container_type = container_type
        self.container_id = container_id
        self.organization_id = org_id
        self._load_fields(field_list, field_values)
        self._display = display_names if display_names else {}
        self.is_deprecated = is_deprecated
        self._validation_config = {"fields": {}, "self": []}

    def add_field_validator(self, field_name, validator):
        if field_name not in self._validation_config["fields"]:
            self._validation_config["fields"][field_name] = []
        self._validation_config["fields"][field_name].append(validator)

    def add_self_validator(self, validator):
        self._validation_config["self"].append(validator)

    def validate(self, parent_path=None, memo=None):
        my_id = f"{self.container_type}#{self.container_id}"
        if memo is None:
            memo = []
        if my_id in memo:
            return []
        memo.append(my_id)
        errors = []
        if parent_path is None:
            parent_path = [self.label()]
        else:
            parent_path = parent_path.copy()
            parent_path.append(self.label())
        for fn in self._fields:
            obj_path = parent_path.copy()
            obj_path.append(self._fields[fn].label())
            if fn in self._validation_config["fields"]:
                for validator in self._validation_config["fields"][fn]:
                    errors.extend(validator.validate(obj_path, self._fields[fn], memo))
            errors.extend(self._fields[fn].validate(obj_path, memo))
        for validator in self._validation_config["self"]:
            errors.extend(validator.validate(parent_path, self, memo))
        return errors

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
                return ""

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
                self._fields[fn].value = self._fields[fn].sanitize_form_input(form_data[fn])

    def set_display_name(self, lang, name):
        self._display[lang] = name

    def label(self):
        return MultiLanguageString(self._display)

    def display_names(self):
        return self._display


class ValidationResult:

    def __init__(self, str_key, object_path, level, profile=None):
        self.level = level
        self.object_path = object_path
        self.str_key = str_key
        self.profile = profile

    def display_text(self):
        return gettext(self.str_key)

    def display_path(self):
        return " > ".join(str(x) for x in self.object_path)


class RequiredFieldValidator:

    def __init__(self, profile=None):
        self.profile = profile

    def validate(self, object_path, field: Field, memo):
        if field.is_empty():
            return [ValidationResult("pipeman.validation.required", object_path, "error", self.profile)]
        return []


class RecommendedFieldValidator:

    def __init__(self, profile=None):
        self.profile = profile

    def validate(self, object_path, field: Field, memo):
        if field.is_empty():
            return [ValidationResult("pipeman.validation.recommended", object_path, "warning", self.profile)]
        return []


class CustomValidator:

    def __init__(self, cb, profile=None):
        self.cb = load_object(cb)
        self.profile = profile

    def validate(self, object_path, obj, memo):
        for error in self.cb(obj, object_path, self.profile, memo):
            level = "error"
            if not isinstance(error, str):
                error, level = error[0], error[1]
            yield ValidationResult(error, object_path, level, self.profile)


class Entity(FieldContainer):

    creator: FieldCreator = None

    @injector.construct
    def __init__(self, entity_type, field_list: dict, is_component: bool, field_values: dict = None, display_names: dict = None,
                 db_id: int = None, ed_id: int = None, is_deprecated: bool = False, org_id: int = None, dataset_id=None):
        super().__init__("entity", db_id, field_list, field_values, display_names, is_deprecated, org_id)
        self.is_component = is_component
        self.entity_type = entity_type
        self.db_id = db_id
        self.entity_data_id = ed_id
        self.dataset_id = dataset_id

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
