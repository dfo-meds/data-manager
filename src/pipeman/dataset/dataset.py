from autoinject import injector
from pipeman.util import deep_update, load_object
from pipeman.entity import FieldContainer
import typing as t
from pipeman.i18n import MultiLanguageString, gettext
import copy
from pipeman.workflow import WorkflowRegistry
import logging
import flask


@injector.injectable_global
class MetadataRegistry:

    def __init__(self):
        self._fields = {}
        self._profiles = {}
        self._display_groups = {}
        self._security_labels = {}
        self._dataset_output_processing_hooks = []

    def register_metadata_processor(self, cb):
        self._dataset_output_processing_hooks.append(cb)

    def security_labels_for_select(self):
        return [
            (x, MultiLanguageString(self._security_labels[x]))
            for x in self._security_labels
        ]

    def security_label_display(self, name):
        return MultiLanguageString(self._security_labels[name]) if name in self._security_labels else ""

    def register_security_label(self, name, labels: dict = None):
        if name in self._security_labels and labels:
            self._security_labels[name].update(labels)
        else:
            self._security_labels[name] = labels if labels else {}

    def register_security_labels_from_dict(self, d: dict):
        if d:
            self._security_labels.update(d)

    def display_group_exists(self, display_group):
        return display_group in self._display_groups

    def display_group_label(self, display_group):
        return MultiLanguageString(self._display_groups[display_group]['labels'])

    def ordered_groups(self, display_groups):
        reordered = [copy.deepcopy(self._display_groups[dg]) for dg in display_groups if dg in self._display_groups]
        reordered.sort(key=lambda x: x['order'])
        for x in reordered:
            yield x['name']

    def register_display_group(self, name, displays=None, order=None):
        if name in self._display_groups:
            if displays:
                self._display_groups[name]["labels"].update(displays)
            if order:
                self._display_groups[name]["order"] = order
        else:
            if order is None:
                order = max(self._display_groups[dg]["order"] for dg in self._display_groups) if self._display_groups else 0
                order += 1
            self._display_groups[name] = {
                "labels": displays if displays else {},
                "order": order,
                "name": name
            }

    def register_field(self, field_name, field_config):
        if field_name in self._fields:
            deep_update(self._fields[field_name], field_config)
        else:
            self._fields[field_name] = field_config

    def register_fields_from_dict(self, d: dict, with_display_group_parents: bool = True):
        if d:
            if with_display_group_parents:
                for dg_name in d:
                    self.register_display_group(
                        dg_name,
                        d[dg_name]["label"] if "label" in d[dg_name] else {},
                        d[dg_name]["order"] if "order" in d[dg_name] else None
                    )
                    if "fields" in d[dg_name]:
                        for fn in d[dg_name]["fields"]:
                            d[dg_name]["fields"][fn]["display_group"] = dg_name
                            self.register_field(fn, d[dg_name]["fields"][fn])
            else:
                deep_update(self._fields, d)

    def register_profile(self, profile_name, display_names, field_list, formatters, preprocess=None):
        if profile_name in self._profiles:
            if display_names:
                deep_update(self._profiles[profile_name]["label"], display_names)
            if field_list:
                deep_update(self._profiles[profile_name]["fields"], field_list)
            if formatters:
                deep_update(self._profiles[profile_name]["formatters"], formatters)
            if preprocess:
                self._profiles[profile_name]["preprocess"] = preprocess
        else:
            self._profiles[profile_name] = {
                "label": display_names or {},
                "fields": field_list or {},
                "formatters": formatters or {},
                "preprocess": preprocess or None
            }

    def register_profiles_from_dict(self, d: dict):
        if d:
            deep_update(self._profiles, d)

    def profiles_for_select(self):
        return [
            (x, MultiLanguageString(self._profiles[x]["label"]))
            for x in self._profiles
        ]

    def metadata_format_exists(self, profile_name, format_name):
        if profile_name not in self._profiles:
            return False
        if format_name not in self._profiles[profile_name]['formatters']:
            return False
        return True

    def metadata_processors(self, profile_name, format_name):
        for hook in self._dataset_output_processing_hooks:
            yield load_object(hook)
        formatter = self._profiles[profile_name]["formatters"][format_name]
        if "preprocess" in formatter and formatter["preprocess"]:
            yield load_object(formatter['preprocess'])

    def metadata_formats(self, profile_name):
        return set((profile_name, x) for x in self._profiles[profile_name]['formatters'].keys()) if profile_name in self._profiles else set()

    def metadata_format_template(self, profile_name, format_name):
        return self._profiles[profile_name]["formatters"][format_name]["template"]

    def metadata_format_link(self, profile_name, format_name, dataset_id, revision_no):
        link = flask.url_for(
            "core.generate_metadata_format",
            profile_name=profile_name,
            format_name=format_name,
            dataset_id=dataset_id,
            revision_no=revision_no
        )
        text = MultiLanguageString(self._profiles[profile_name]["formatters"][format_name]["label"])
        return link, text

    def build_dataset(self, profiles, dataset_values = None, dataset_id = None, ds_data_id = None, display_names=None, is_deprecated=False, org_id=None, extras=None, users=None):
        fields = set()
        mandatory = set()
        for profile in profiles:
            if profile in self._profiles:
                fields.update(self._profiles[profile]["fields"].keys())
                mandatory.update(x for x in self._profiles[profile]["fields"].keys() if self._profiles[profile]["fields"][x])
        field_list = {}
        for fn in fields:
            if fn not in self._fields:
                logging.getLogger("pipeman.fields").error(f"Field {fn} not defined, skipping")
            else:
                field_list[fn] = self._fields[fn]
        return Dataset(field_list, dataset_values, display_names, mandatory, dataset_id, profiles, ds_data_id, is_deprecated, org_id, extras, users)


class Dataset(FieldContainer):

    mreg: MetadataRegistry = None

    @injector.construct
    def __init__(self, field_list: dict, field_values: t.Optional[dict], display_names: t.Optional[dict], required_fields, dataset_id, profiles, ds_data_id, is_deprecated: bool = False, org_id: int = None, extras: dict = None, users: list = None):
        super().__init__(dataset_id, field_list, field_values, display_names, is_deprecated, org_id)
        self.required_fields = required_fields
        self.profiles = profiles
        self.dataset_id = dataset_id
        self.metadata_id = ds_data_id
        self.extras = extras or {}
        self.users = []

    def keywords(self, language=None):
        keywords = set()
        for fn in self._fields:
            keywords.update(self._fields[fn].get_keywords(language))
        return keywords

    def metadata_format_links(self):
        formats = set()
        for profile in self.profiles:
            formats.update(self.mreg.metadata_formats(profile))
        for f in formats:
            yield self.mreg.metadata_format_link(*f, self.dataset_id, self.metadata_id)

    def status(self):
        return self.extras["status"] if "status" in self.extras else None

    def status_display(self):
        stat = self.status()
        if stat is None or stat == "":
            return gettext("pipeman.status.unknown")
        return gettext(f"pipeman.dataset.status.{stat.lower()}")

    @injector.inject
    def pub_workflow_display(self, wreg: WorkflowRegistry = None):
        return wreg.workflow_display("dataset_publication", self.extras["pub_workflow"])

    @injector.inject
    def act_workflow_display(self, wreg: WorkflowRegistry = None):
        return wreg.workflow_display("dataset_activation", self.extras["act_workflow"])

    @injector.inject
    def security_level_display(self, reg: MetadataRegistry = None):
        return reg.security_label_display(self.extras["security_level"])

    def properties(self):
        return [
            ('pipeman.dataset.status', self.status_display()),
            ('pipeman.dataset.act_workflow', self.act_workflow_display()),
            ('pipeman.dataset.pub_workflow', self.pub_workflow_display()),
            ('pipeman.dataset.security_level', self.security_level_display()),
        ]
