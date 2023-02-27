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

    def register_type(self, key, display_names, field_config, derived_config, validation, is_component: bool = None):
        if key in self._entity_types:
            deep_update(self._entity_types[key]["display"], display_names)
            deep_update(self._entity_types[key]["fields"], field_config)
            deep_update(self._entity_types[key]["validation"], validation)
            deep_update(self._entity_types[key]["derived_fields"], derived_config)
            if is_component is not None:
                self._entity_types[key]['is_component'] = is_component
        else:
            self._entity_types[key] = {
                "display": display_names,
                "fields": field_config,
                "is_component": bool(is_component),
                "validation": validation,
                "derived_fields": derived_config
            }

    def register_from_dict(self, cfg_dict):
        if cfg_dict:
            for key in cfg_dict:
                self.register_type(
                    key,
                    cfg_dict[key]["display"] if "display" in cfg_dict[key] else {},
                    cfg_dict[key]["fields"] if "fields" in cfg_dict[key] else {},
                    cfg_dict[key]["derived_fields"] if "derived_fields" in cfg_dict[key] else {},
                    cfg_dict[key]["validation"] if "validation" in cfg_dict[key] else {},
                    cfg_dict[key]["is_component"] if "is_component" in cfg_dict[key] else None
                )

    def display(self, key):
        keys = self._entity_types[key]["display"].copy()
        keys['und'] = key
        return MultiLanguageString(keys)

    def new_entity(self, key, **kwargs):
        ent = Entity(
            key,
            field_list=self._entity_types[key]["fields"],
            is_component=self._entity_types[key]["is_component"],
            **kwargs
        )
        if "derived_fields" in self._entity_types[key] and self._entity_types[key]["derived_fields"]:
            dfns = self._entity_types[key]["derived_fields"]
            for dfn in dfns:
                ent.add_derived_field(dfn, dfns[dfn]["label"], dfns[dfn]["value_function"])
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


def combine_object_path(parent_path, sub_path):
    if parent_path is None:
        return sub_path.copy()
    new_path = parent_path.copy()
    new_path.extend(sub_path)
    return new_path


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
        self._derived_fields = {}

    def field_label(self, fn):
        return self._fields[fn].label()

    def add_derived_field(self, field_name, field_label, field_cb):
        self._derived_fields[field_name] = {
            "label": field_label,
            "cb": field_cb
        }

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
        parent_path = combine_object_path(parent_path, [self.label()])
        fns = list(self._fields.keys())
        fns.sort()
        for fn in fns:
            obj_path = combine_object_path(parent_path, [self._fields[fn].label()])
            if fn in self._validation_config["fields"]:
                for validator in self._validation_config["fields"][fn]:
                    errors.extend(validator.validate(obj_path, self._fields[fn], memo))
            errors.extend(self._fields[fn].validate(obj_path, memo))
            for entity in self._fields[fn].related_entities():
                errors.extend(entity.validate(obj_path, memo))
        for validator in self._validation_config["self"]:
            errors.extend(validator.validate(parent_path, self, memo))
        return errors

    def _load_fields(self, field_list: dict, field_values: dict = None):
        for field_name in field_list:
            field_config = copy.deepcopy(field_list[field_name])
            self._fields[field_name] = self.creator.build_field(field_name, field_config.pop('data_type'), field_config, self.container_type, self.container_id)
            if field_values and field_name in field_values:
                self._fields[field_name].value = self._fields[field_name].unserialize(field_values[field_name])

    def display_values(self, display_group = None):
        if display_group == "__derived__":
            keys = list(self._derived_fields.keys())
            keys.sort()
            for key in keys:
                yield MultiLanguageString(self._derived_fields[key]["label"], load_object(self._derived_fields[key]["cb"])(self))
        else:
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
        if display_group == "__derived__":
            return bool(self._derived_fields)
        return any(self._fields[fn].display_group == display_group for fn in self._fields)

    def supported_display_groups(self) -> set:
        dg = set(self._fields[fn].display_group for fn in self._fields)
        if self._derived_fields:
            dg.add("__derived__")
        return dg

    def __html__(self):
        return str(self)

    @cache
    def data(self, key, **kwargs):
        if key in self._derived_fields:
            try:
                return load_object(self._derived_fields[key]['cb'])(self)
            except Exception as ex:
                print(ex)
        if key in self._fields:
            try:
                return self._fields[key].data(**kwargs)
            except Exception as ex:
                print(ex)
        return ""

    def __contains__(self, item):
        return item in self._fields or item in self._derived_fields

    def __getitem__(self, key):
        if key not in self._fields and key not in self._derived_fields:
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

    def __init__(self, str_key, object_path, level, code, profile=None):
        self.level = level
        self.object_path = object_path
        self.str_key = str_key
        self.profile = profile
        self.code = code

    def display_text(self):
        return gettext(self.str_key)

    def display_path(self):
        return " > ".join(str(x) for x in self.object_path)


class RequiredFieldValidator:

    def __init__(self, profile=None):
        self.profile = profile

    def validate(self, object_path, field: Field, memo):
        if field.is_empty():
            return [ValidationResult("pipeman.validation.required", object_path, "error", "CRE-01", self.profile)]
        return []


class RecommendedFieldValidator:

    def __init__(self, profile=None):
        self.profile = profile

    def validate(self, object_path, field: Field, memo):
        if field.is_empty():
            return [ValidationResult("pipeman.validation.recommended", object_path, "warning", "CRE-02", self.profile)]
        return []


class CustomValidator:

    def __init__(self, cb, profile=None):
        self.cb = load_object(cb)
        self.profile = profile

    def validate(self, object_path, obj, memo):
        for error in self.cb(obj, object_path, self.profile, memo):
            if isinstance(error, ValidationResult):
                yield error
            else:
                str_error = ""
                level = "error"
                code = "CRE-00"
                if not isinstance(error, str):
                    if len(error) >= 2:
                        str_error, code = error[0], error[1]
                    if len(error) >= 3:
                        level = error[2]
                yield ValidationResult(str_error, object_path, level, code, self.profile)


class Entity(FieldContainer):

    creator: FieldCreator = None

    @injector.construct
    def __init__(self, entity_type, is_component: bool, db_id: int = None, ed_id: int = None, parent_id=None, parent_type=None, **kwargs):
        super().__init__("entity", db_id, **kwargs)
        self.is_component = is_component
        self.entity_type = entity_type
        self.db_id = db_id
        self.entity_data_id = ed_id
        self.parent_id = parent_id
        self.parent_type = parent_type

    def view_link(self):
        return flask.url_for("core.view_entity", obj_type=self.entity_type, obj_id=self.db_id)

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
