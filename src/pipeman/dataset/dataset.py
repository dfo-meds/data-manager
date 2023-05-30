import markupsafe
from autoinject import injector
from pipeman.util import deep_update, load_object
from pipeman.entity import FieldContainer
from pipeman.entity.entity import CustomValidator, RecommendedFieldValidator, RequiredFieldValidator
from pipeman.db import BaseObjectRegistry
from pipeman.i18n import MultiLanguageString, gettext, MultiLanguageLink
import copy
from pipeman.workflow import WorkflowRegistry
import logging
import flask
import yaml


@injector.injectable_global
class MetadataRegistry:

    def __init__(self):
        self._fields = BaseObjectRegistry("field")
        self._profiles = BaseObjectRegistry("profile")
        self._display_groups = BaseObjectRegistry("display_group")
        self._security_labels = BaseObjectRegistry("security_label")
        self._dataset_output_processing_hooks = []

    def __cleanup__(self):
        self._fields.__cleanup__()
        self._profiles.__cleanup__()
        self._display_groups.__cleanup__()
        self._security_labels.__cleanup__()

    def reload_types(self):
        self._fields.reload_types()
        self._profiles.reload_types()
        self._display_groups.reload_types()
        self._security_labels.reload_types()

    def register_metadata_processor(self, cb):
        self._dataset_output_processing_hooks.append(cb)

    def security_labels_for_select(self):
        return [
            (x, MultiLanguageString(self._security_labels[x]))
            for x in self._security_labels
        ]

    def security_label_display(self, name):
        return MultiLanguageString(self._security_labels[name]) if name in self._security_labels else name

    def register_security_label(self, name, **config):
        self._security_labels.register(name, **config)

    def register_security_labels_from_dict(self, d: dict):
        self._security_labels.register_from_dict(d)

    def register_security_labels_from_yaml(self, yaml_file):
        self._security_labels.register_from_yaml(yaml_file)

    def display_group_exists(self, display_group):
        return display_group in self._display_groups

    def display_group_label(self, display_group):
        return MultiLanguageString(self._display_groups[display_group]['display'])

    def ordered_groups(self, display_groups):
        reordered = [copy.deepcopy(self._display_groups[dg]) for dg in display_groups if dg in self._display_groups]
        reordered.sort(key=lambda x: x['order'])
        for x in reordered:
            yield x['name']

    def register_display_group(self, name, order, **config):
        if order is None:
            order = max(self._display_groups[dg]["order"] if "order" in self._display_groups[dg] else 1 for dg in self._display_groups) if self._display_groups else 0
            order += 1
        config['name'] = name
        self._display_groups.register(name, order=order, **config)

    def register_field(self, field_name, **config):
        self._fields.register(field_name, **config)

    def register_metadata_from_dict(self, d: dict):
        for dg_name in d or []:
            self.register_display_group(
                dg_name,
                display=d[dg_name]["display"] if "display" in d[dg_name] else {},
                order=d[dg_name]["order"] if "order" in d[dg_name] else None
            )
            if "fields" in d[dg_name]:
                for fn in d[dg_name]["fields"]:
                    d[dg_name]["fields"][fn]["display_group"] = dg_name
                    self.register_field(fn, **d[dg_name]["fields"][fn])

    def register_metadata_from_yaml(self, yaml_file):
        with open(yaml_file, "r", encoding="utf-8") as h:
            self.register_metadata_from_dict(yaml.safe_load(h))

    def register_profile(self, profile_name, **config):
        self._profiles.register(profile_name, **config)

    def register_profiles_from_dict(self, d: dict):
        self._profiles.register_from_dict(d)

    def register_profiles_from_yaml(self, yaml_file):
        self._profiles.register_from_yaml(yaml_file)

    def profiles_for_select(self):
        return [
            (x, MultiLanguageString(self._profiles[x]["display"]))
            for x in self._profiles
        ]

    def metadata_format_exists(self, profile_name, format_name):
        if profile_name not in self._profiles:
            return False
        if format_name not in self._profiles[profile_name]['formatters']:
            return False
        return True

    def metadata_processors(self, profiles, profile_name, format_name):
        for hook in self._dataset_output_processing_hooks:
            yield load_object(hook)
        for prof in profiles:
            if 'preprocess' in self._profiles[prof] and self._profiles[prof]['preprocess']:
                for hook in self._profiles[prof]['preprocess']:
                    yield load_object(hook)
        formatter = self._profiles[profile_name]["formatters"][format_name]
        if "preprocess" in formatter and formatter["preprocess"]:
            yield load_object(formatter['preprocess'])

    def metadata_formats(self, profile_name):
        if 'formatters' in self._profiles[profile_name]:
            return set((profile_name, x) for x in self._profiles[profile_name]['formatters'].keys()) if profile_name in self._profiles else set()
        return set()

    def metadata_format_template(self, profile_name, format_name):
        return self._profiles[profile_name]["formatters"][format_name]["template"]

    def metadata_format_content_type(self, profile_name, format_name):
        # Defaults
        encoding = "utf-8"
        mime_type = "text/plain"
        template_name = self._profiles[profile_name]["formatters"][format_name]["template"].lower()
        extension = template_name[template_name.rfind(".") + 1:] if "." in template_name else ""
        # What were we told?
        if "extension" in self._profiles[profile_name]["formatters"][format_name] and self._profiles[profile_name]["formatters"][format_name]["extension"]:
            extension = self._profiles[profile_name]["formatters"][format_name]["extension"]
        if "content_type" in self._profiles[profile_name]["formatters"][format_name] and self._profiles[profile_name]["formatters"][format_name]["content_type"]:
            mime_type = self._profiles[profile_name]["formatters"][format_name]["content_type"]
        elif template_name.endswith(".xml"):
            mime_type = "text/xml"
        elif template_name.endswith(".html") or template_name.endswith(".htm"):
            mime_type = "text/html"
            extension = "html"
        elif template_name.endswith(".rdf"):
            mime_type = "application/rdf+xml"
            extension = "rdf"
        elif template_name.endswith(".jsonld"):
            mime_type = "application/ld+json"
            extension = "jsonlod"
        if "encoding" in self._profiles[profile_name]["formatters"][format_name]:
            encoding = self._profiles[profile_name]["formatters"][format_name] or "utf-8"
        return mime_type, encoding, extension

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

    def set_metadata_from_file(self, dataset, file_type: str, file_metadata: dict):
        for p in dataset.profiles:
            if p in self._profiles and "mappers" in self._profiles[p] and file_type in self._profiles[p]["mappers"]:
                obj_name = self._profiles[p]["mappers"][file_type]
                obj = load_object(obj_name)
                obj(dataset, file_type, file_metadata)

    def build_dataset(self, profiles, **kwargs):
        fields = set()
        ext_profiles = set()
        while profiles:
            p = profiles.pop()
            if p in self._profiles and p not in ext_profiles:
                ext_profiles.add(p)
                if "extends" in self._profiles[p] and self._profiles[p]["extends"]:
                    profiles.append(self._profiles[p]["extends"])
        for profile in ext_profiles:
            if "fields" in self._profiles[profile] and self._profiles[profile]["fields"]:
                fields.update(self._profiles[profile]["fields"].keys())
        field_list = {}
        for fn in fields:
            if fn not in self._fields:
                logging.getLogger("pipeman.fields").error(f"Field {fn} not defined, skipping")
            else:
                field_list[fn] = self._fields[fn]
        ds = Dataset(field_list=field_list, profiles=ext_profiles, **kwargs)
        for profile in ext_profiles:
            if "derived_fields" in self._profiles[profile] and self._profiles[profile]["derived_fields"]:
                dfns = self._profiles[profile]["derived_fields"]
                for dfn in dfns:
                    ds.add_derived_field(dfn, dfns[dfn]["label"], dfns[dfn]["value_function"])
            pn = MultiLanguageString(self._profiles[profile]["display"])
            if "validation" in self._profiles[profile] and self._profiles[profile]["validation"]:
                validation = self._profiles[profile]["validation"]
                if 'required' in validation and validation['required']:
                    for fn in validation['required']:
                        ds.add_field_validator(fn, RequiredFieldValidator(pn))
                if 'recommended' in validation and validation['recommended']:
                    for fn in validation['recommended']:
                        ds.add_field_validator(fn, RecommendedFieldValidator(pn))
                if 'custom' in validation and validation['custom']:
                    for call in validation['custom']:
                        ds.add_self_validator(CustomValidator(call, pn))
        return ds


class Dataset(FieldContainer):

    mreg: MetadataRegistry = None

    @injector.construct
    def __init__(self, profiles, dataset_id=None, ds_data_id=None, revision_no=None, extras: dict = None, users: list = None, **kwargs):
        super().__init__("dataset", dataset_id, **kwargs)
        self.profiles = profiles
        self.dataset_id = dataset_id
        self.metadata_id = ds_data_id
        self.revision_no = revision_no
        self.extras = extras or {}
        self.users = users

    def set_from_file_metadata(self, file_type: str, file_metadata: dict):
        self.mreg.set_metadata_from_file(self, file_type, file_metadata)

    def revision_published_date(self):
        return self.extras["pub_date"] if "pub_date" in self.extras else None

    def view_link(self):
        return flask.url_for("core.view_dataset", dataset_id=self.container_id)

    def guid(self):
        return self.extras['guid'] if 'guid' in self.extras else ""

    def created_date(self):
        return self.extras['created_date']

    def modified_date(self):
        return self.extras['modified_date']

    def keywords(self):
        keywords = []
        for fn in self._fields:
            keywords.extend(self._fields[fn].get_keywords())
        return keywords

    def metadata_format_links(self):
        formats = set()
        for profile in self.profiles:
            formats.update(self.mreg.metadata_formats(profile))
        formats = list(formats)
        formats.sort(key=lambda x: f"{x[0]}{x[1]}")
        for f in formats:
            yield self.mreg.metadata_format_link(*f, self.dataset_id, self.revision_no)

    def status(self):
        return self.extras["status"] if "status" in self.extras else None

    def status_display(self):
        stat = self.status()
        if stat is None or stat == "":
            return gettext("pipeman.label.dataset.status.unknown")
        return gettext(f"pipeman.label.dataset.status.{stat.lower()}")
        # gettext('pipeman.label.dataset.status.under_review')
        # gettext('pipeman.label.dataset.status.active')
        # gettext('pipeman.label.dataset.status.draft')

    @injector.inject
    def pub_workflow_display(self, wreg: WorkflowRegistry = None):
        return wreg.workflow_display("dataset_publication", self.extras["pub_workflow"])

    @injector.inject
    def act_workflow_display(self, wreg: WorkflowRegistry = None):
        return wreg.workflow_display("dataset_activation", self.extras["act_workflow"])

    @injector.inject
    def security_level_display(self, reg: MetadataRegistry = None):
        return reg.security_label_display(self.extras["security_level"])

    def activation_chain_display(self):
        link = flask.url_for('core.view_item', item_id=self.extras['activated_item_id'])
        text = gettext("pipeman.label.dataset.activation_chain_link")
        return markupsafe.Markup(f"<a href='{link}'>{markupsafe.escape(text)}</a>")

    def properties(self):
        props = [
            ('pipeman.label.dataset.status', self.status_display()), # gettext('pipeman.label.dataset.status')
            ('pipeman.label.dataset.activation_workflow', self.act_workflow_display()), # gettext('pipeman.label.dataset.activation_workflow')
            ('pipeman.label.dataset.publication_workflow', self.pub_workflow_display()),  # gettext('pipeman.label.dataset.publication_workflow')
            ('pipeman.label.dataset.security_level', self.security_level_display()),  #gettext('pipeman.label.dataset.security_level')
            ('pipeman.label.dataset.guid', self.guid()),  # gettext('pipeman.label.dataset.guid')
        ]
        if 'activated_item_id' in self.extras and self.extras['activated_item_id']:
            props.append((
                'pipeman.label.dataset.activation_chain',  # gettext('pipeman.label.dataset.activation_chain')
                self.activation_chain_display()
            ))
        return props
