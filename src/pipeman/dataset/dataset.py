from autoinject import injector
from pipeman.util import deep_update
from pipeman.entity import FieldContainer
import typing as t


@injector.injectable_global
class MetadataRegistry:

    def __init__(self):
        self._fields = {}
        self._profiles = {}

    def register_field(self, field_name, field_config):
        if field_name in self._fields:
            deep_update(self._fields[field_name], field_config)
        else:
            self._fields[field_name] = field_config

    def register_fields_from_dict(self, d: dict):
        if d:
            deep_update(self._fields, d)

    def register_profile(self, profile_name, display_names, field_list, formatters):
        if profile_name in self._profiles:
            if display_names:
                deep_update(self._profiles[profile_name]["label"], display_names)
            if field_list:
                deep_update(self._profiles[profile_name]["fields"], field_list)
            if formatters:
                deep_update(self._profiles[profile_name]["formatters"], formatters)
        else:
            self._profiles[profile_name] = {
                "label": display_names or {},
                "fields": field_list or {},
                "formatters": formatters or {},
            }

    def register_profiles_from_dict(self, d: dict):
        if d:
            deep_update(self._profiles, d)

    def metadata_format_exists(self, profile_name, format_name):
        if profile_name not in self._profiles:
            return False
        if format_name not in self._profiles[profile_name]['formatters']:
            return False
        return True

    def metadata_format_template(self, profile_name, format_name):
        return self._profiles[profile_name]["formatters"][format_name]["template"]

    def build_dataset(self, profiles, dataset_values = None, dataset_id = None, ds_data_id = None, display_names=None, is_deprecated=False, org_id=None, extras=None, users=None):
        fields = set()
        mandatory = set()
        for profile in profiles:
            if profile in self._profiles:
                fields.update(self._profiles[profile]["fields"].keys())
                mandatory.update(x for x in self._profiles["fields"].keys() if self._profiles["fields"][x])
        field_list = {
            fn: self._fields[fn] for fn in fields
        }
        return Dataset(field_list, dataset_values, display_names, mandatory, dataset_id, profiles, ds_data_id, is_deprecated, org_id, extras, users)


class Dataset(FieldContainer):

    def __init__(self, field_list: dict, field_values: t.Optional[dict], display_names: t.Optional[dict], required_fields, dataset_id, profiles, ds_data_id, is_deprecated: bool = False, org_id: int = None, extras: dict = None, users: list = None):
        super().__init__(field_list, field_values, display_names, is_deprecated, org_id)
        self.required_fields = required_fields
        self.profiles = profiles
        self.dataset_id = dataset_id
        self.metadata_id = ds_data_id
        self.extras = extras or {}
        self.users = []

    def status(self):
        return self.extras["status"] if "status" in self.extras else None
