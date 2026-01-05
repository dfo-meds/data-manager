import typing as t

import wtforms as wtf
import wtforms.validators as wtfv
from autoinject import injector
import zrlog

from pipeman.i18n import MultiLanguageString, DelayedTranslationString, TranslationManager
from pipeman.util.flask import TranslatableField, NoControlCharacters, flasht
from pipeman.entity.keywords import Keyword
from pipeman.entity.util import HtmlList, _render_mls


class Field:

    tm: TranslationManager = None

    @injector.construct
    def __init__(self, field_name, field_config, container=None):

        self.field_name = field_name
        self.field_config = field_config
        self.display_group = field_config['display_group'] if 'display_group' in field_config else ""
        self.order = field_config['order'] if 'order' in field_config else 0
        self.value = None
        self._use_default_repeatable = True
        self.parent = container
        self.parent_id = self.parent.container_id if self.parent else None
        self.parent_type = self.parent.container_type if self.parent else None
        self._default_thesaurus = None
        self._log = zrlog.get_logger("pipeman.field")

    def allow_javascript_controls(self):
        from pipeman.entity import Entity
        # TODO: Select2 doesn't work well under these conditions, but we could probably fix it later.
        if isinstance(self.parent, Entity) and self.parent.parent_type == '_field_repeatable':
            return False
        return True

    def is_equal(self, other_value):
        return self.serialize(self.value) == self.serialize(other_value)

    def config(self, *keys, default=None):
        working = self.field_config
        for k in keys:
            if not (isinstance(working, dict) and k in working):
                return default
            working = working[k]
        return working

    def sanitize_form_input(self, val):
        if self.allow_translation_requests():
            if self.is_repeatable() and isinstance(val, list):
                for k in val:
                    if isinstance(val[k], dict) and '_translation_request' in val and val['_translation_request']:
                        self._file_translation_request(val[k], k)
                    elif k in self.value and '_translation_request' in self.value[k] and self.value[k]['_translation_request']:
                        val[k]['_translation_request'] = True
            elif isinstance(val, dict):
                if val and "_translation_request" in val and val["_translation_request"]:
                    self._file_translation_request(val)
                elif self.value and '_translation_request' in self.value and self.value['_translation_request']:
                    val['_translation_request'] = True
        if self.is_multilingual():
            if self.is_repeatable():
                for idx in range(0, min(len(val), len(self.value))):
                    for k in self.value[idx]:
                        if k not in val[idx]:
                            val[idx][k] = self.value[idx][k]
            else:
                for k in self.value:
                    if k not in val:
                        val[k] = self.value[k]
        return val

    def set_from_translation(self, val: dict = None, index: int = None):
        if index is not None:
            if index not in self.value:
                raise ValueError(f"No such index {index} in {self.parent_type}.{self.parent_id}.{self.field_name}")
            self._set_from_translation(self.value[index], val)
        else:
            self._set_from_translation(self.value, val)

    def _set_from_translation(self, current_value, new_value):
        if not isinstance(current_value, dict):
            raise ValueError(f"Field {self.parent_type}.{self.parent_id}.{self.field_name} no longer supports translations")
        if new_value is not None:
            current_value.update(new_value)
        current_value["_translation_request"] = False

    @injector.inject
    def _file_translation_request(self, val: dict, index: int = None, wc: "pipeman.workflow.controller.WorkflowController" = None):
        if not any(val[x] and x not in ('_translation_request', 'und') for x in val):
            flasht("pipeman.field.error.translation_nothing_to_work_with", "warning", field_name=self.field_name, index=index)
            val['_translation_request'] = False
            return
        if all(val[x] or x in ('_translation_request', 'und') for x in val):
            flasht("pipeman.field.error.translation_nothing_to_do", "warning", field_name=self.field_name, index=index)
            val['_translation_request'] = False
            return
        if wc.check_exists(
            'text_translation',
            'default',
            object_type=self.parent_type,
            object_id=self.parent_id,
            context_filters={
                'field_name': self.field_name,
                'type': 'field',
                'index': index
            }
        ):
            flasht("pipeman.field.error.translation_already_in_progress", "warning", field_name=self.field_name, index=index)
            return
        ctx = {
            'object_type': self.parent_type,
            'object_id': self.parent_id,
            'field_name': self.field_name,
            'text_values': val,
            'type': "field",
            'index': index
        }
        wc.start_workflow('text_translation', 'default', ctx, self.parent_id, self.parent_type)
        flasht("pipeman.field.messages.translation_requested", "success", field_name=self.field_name, index=index)

    def is_multilingual(self):
        return self.config("multilingual", default=False)

    def is_repeatable(self):
        return self.config("repeatable", default=False)

    def allow_translation_requests(self):
        if not self.config("allow_translation_requests", default=self.is_multilingual()):
            return False
        if self.parent_type is None or self.parent_id is None:
            return False
        return True

    def set_from_external(self, external_value, external_container_setter: callable):
        self.set_from_raw(external_value)

    def set_from_raw(self, raw_value):
        if self.is_repeatable():
            if isinstance(raw_value, set) or isinstance(raw_value, list) or isinstance(raw_value, tuple):
                if self.is_multilingual():
                    self.value = [
                        ({x: self._handle_raw(x) for x in y}
                        if isinstance(y, dict)
                        else {'und': self._handle_raw(y)})

                        for y in raw_value
                    ]
                else:
                    self.value = [self._handle_raw(x) for x in raw_value]
            else:
                if self.is_multilingual():
                    self.value = [
                        {x: self._handle_raw(raw_value[x]) for x in raw_value}
                        if isinstance(raw_value, dict)
                        else {'und': raw_value}
                    ]
                else:
                    self.value = [self._handle_raw(raw_value)]
        elif self.is_multilingual():
            if isinstance(raw_value, dict):
                self.value = {x: self._handle_raw(raw_value[x]) for x in raw_value}
            else:
                self.value = {'und': self._handle_raw(raw_value)}
        else:
            self.value = self._handle_raw(raw_value)

    def _handle_raw(self, raw_value):
        return raw_value

    def is_empty(self):
        if self.value is None or self.value == [] or self.value == "":
            return True
        if self.is_repeatable():
            for val in self.value:
                if self.is_multilingual():
                    return all(self._is_empty(val[x]) for x in val if x != '_translation_request')
                elif not self._is_empty(val):
                    return False
            return True
        elif self.is_multilingual():
            return all(self._is_empty(self.value[x]) for x in self.value if x != '_translation_request')
        else:
            return self._is_empty(self.value)

    def _is_empty(self, val):
        return val is None or val == "" or val == [] or val == {}

    def serialize(self, val):
        if self.is_repeatable():
            if isinstance(self.value, list):
                return [self._serialize(x) for x in self.value]
            else:
                return [self._serialize(self.value)]
        return self._serialize(val)

    def unserialize(self, val):
        # TODO: do we need to handle translation here? only if non-text is translated.
        if self.is_repeatable() and not isinstance(val, list):
            return [self._unserialize(val)]
        elif (not self.is_repeatable()) and isinstance(val, list):
            return self._unserialize(val[0]) if val else None
        else:
            return self._unserialize(val)

    def _serialize(self, val):
        return val

    def _unserialize(self, val):
        return val

    def get_keywords(self):
        if not self.value:
            return set()
        if not self.config("keyword_config", "is_keyword", default=False):
            return set()
        return self._extract_keywords()

    def update_from_keyword(self, keyword: str, keyword_dictionary: str = None) -> bool:
        if not self.config("keyword_config", "is_keyword", default=False):
            return False
        if keyword_dictionary is not None:
            prefix = self.config("keyword_config", "thesaurus", "prefix", default = None)
            full_name = self.config("keyword_config", "thesaurus", "citation", "title", "und", default=None)
            if keyword_dictionary not in (prefix, full_name):
                return False
        return self._update_from_keyword(keyword, keyword_dictionary)

    def _update_from_keyword(self, keyword: str, keyword_dictionary: str) -> bool:
        return False

    def keyword_mode(self):
        method = "value"
        method = self.config("keyword_config", "extraction_method", default=method)
        method = self.config("keyword_config", "mode", default=method)
        if method not in ("value", "translate", "both"):
            method = "value"
        return method

    def get_default_thesaurus(self):
        return self.config("keyword_config", "thesaurus", default=None)

    def build_thesaurus(self, loaded_obj=None):
        thesaurus = None
        thesaurus_field = self.config("keyword_config", "thesaurus_field", default=None)
        if loaded_obj is not None and thesaurus_field is not None:
            thesaurus = loaded_obj.data(thesaurus_field)
        return thesaurus if thesaurus else self.get_default_thesaurus()

    def _extract_keywords(self):
        if self.is_repeatable():
            keywords = []
            for value in self.value:
                if value is not None:
                    keywords.append(self._value_to_keyword(value))
            return keywords
        elif self.value is not None:
            return [self._value_to_keyword(self.value)]
        else:
            return []

    def _value_to_keyword(self, value):
        return Keyword(str(value), str(value), None, self.build_thesaurus())

    def control(self) -> wtf.Field:
        ctl_class = self._control_class()
        parent_args, field_args = self._split_args()
        use_multilingual = self.is_multilingual()
        use_repeatable = self.is_repeatable() and self._use_default_repeatable
        if use_repeatable and self.value is None:
            self.value = []
        # TODO: If multilingual, detect and limit values to those identified in metadata languages
        if use_multilingual and use_repeatable:
            min_entries = 1
            return wtf.FieldList(
                TranslatableField(ctl_class,
                                  field_kwargs=field_args,
                                  allow_translation_requests=self.allow_translation_requests(),
                                  use_metadata_languages=True,
                                  label="",
                                  allow_js_widget=self.allow_javascript_controls()
                                  ),
                min_entries=min_entries,
                **parent_args
            )
        elif use_multilingual:
            return TranslatableField(ctl_class,
                                     field_kwargs=field_args,
                                     allow_translation_requests=self.allow_translation_requests(),
                                     allow_js_widget=self.allow_javascript_controls(),
                                     use_metadata_languages=True,
                                     **parent_args)
        elif use_repeatable:
            min_entries = 1
            return wtf.FieldList(ctl_class(label="", **field_args), **parent_args, min_entries=min_entries)
        else:
            return ctl_class(**parent_args, **field_args)

    def _split_args(self) -> (dict, dict):
        parent_args = self._parent_arguments()
        actual_args = self._wtf_arguments()
        parent_list = {}
        field_list = {}
        for k in actual_args:
            if k in parent_args:
                parent_list[k] = actual_args[k]
            else:
                field_list[k] = actual_args[k]
        return parent_list, field_list

    def _control_class(self) -> t.Callable:
        raise NotImplementedError

    def validate(self, obj_path, memo):
        return []

    def related_entities(self):
        return []

    def label(self) -> t.Union[str, MultiLanguageString]:
        txt = self.config("label", default="")
        if isinstance(txt, dict):
            return MultiLanguageString(txt)
        return txt

    def description(self) -> t.Union[str, MultiLanguageString]:
        txt = self.config("description", default="")
        if isinstance(txt, dict):
            return MultiLanguageString(txt)
        return txt

    def filters(self) -> list:
        filters = []
        return filters

    def validators(self) -> list:
        validators = []
        if self.config("is_required", default=False):
            validators.append(wtfv.InputRequired(message=DelayedTranslationString("pipeman.error.required_field")))
        else:
            validators.append(wtfv.Optional())
        return validators

    def default_value(self) -> t.Any:
        if self.is_multilingual():
            metadata_langs = self.tm.metadata_supported_languages()
            if self.is_repeatable():
                return [
                    {
                        x: self.value[x]
                        for x in obj
                        if x in metadata_langs or x == '_translation_request' or x == 'und'
                    }
                    for obj in self.value
                ]
            return {
                x: self.value[x]
                for x in self.value
                if x in metadata_langs or x == '_translation_request' or x == 'und'
            }
        return self.value

    def _wtf_arguments(self) -> dict:
        args = {
            "label": self.label(),
            "description": self.description(),
            "validators": self.validators(),
            "default": self.default_value,
            "filters": self.filters()
        }
        args.update(self._extra_wtf_arguments())
        return args

    def _parent_arguments(self) -> set:
        return {"label", "description", "default"}

    def _extra_wtf_arguments(self) -> dict:
        return {}

    def display(self):
        metadata_langs = self.tm.metadata_supported_languages()
        if self.value is None:
            return ""
        use_multilingual = self.is_multilingual()
        use_repeatable = self.is_repeatable()
        if use_repeatable and use_multilingual:
            items = [
                MultiLanguageString({
                    y: self._format_for_ui(x[y])
                    for y in x
                    if y in metadata_langs or y == 'und'
                })
                for x in self.value
            ]
            return str(HtmlList(items))
        elif use_repeatable:
            items = [self._format_for_ui(x) for x in self.value]
            return str(HtmlList(items))
        elif use_multilingual:
            if isinstance(self.value, str):
                return _render_mls(MultiLanguageString({"und": self.value}))
            return _render_mls(MultiLanguageString({
                x: self._format_for_ui(self.value[x])
                for x in self.value
                if x in metadata_langs or x == 'und'
            }))
        else:
            return self._format_for_ui(self.value)

    def data(self, lang=None, index=None, **kwargs):
        use_multilingual = self.is_multilingual()
        use_repeatable = self.is_repeatable()
        value = self.value
        if value is None:
            return self._process_value(None, **kwargs)
        if index is not None and use_repeatable:
            if index >= len(self.value):
                return self._process_value(None, **kwargs)
            value = self.value[index]
            use_repeatable = False
        if lang is not None and use_multilingual:
            value = self.value[lang]
            use_multilingual = False
        if use_repeatable and use_multilingual:
            return [
                MultiLanguageString({
                    y: self._process_value(value[x][y], **kwargs)
                    for y in x
                })
                for x in value
            ]
        elif use_repeatable:
            d = []
            for v in value:
                pd = self._process_value(v, **kwargs)
                if pd is not None:
                    d.append(pd)
            return d
        elif use_multilingual:
            return MultiLanguageString({
                x: self._process_value(value[x], **kwargs) for x in value
            })
        else:
            return self._process_value(value, **kwargs)

    def _process_value(self, val, none_as_blank=True, **kwargs):
        return "" if val is None and none_as_blank else val

    def _format_for_ui(self, val):
        if val is None:
            return ""
        return str(val)


class NoControlMixin:

    def validators(self):
        validators = super().validators()
        validators.append(NoControlCharacters())
        return validators


class LengthValidationMixin:

    def validators(self):
        validators = super().validators()
        min_val = self.config("min", default=None)
        max_val = self.config("max", default=None)
        if min_val is not None and max_val is not None:
            validators.append(wtfv.Length(
                min=min_val,
                max=max_val,
                message=DelayedTranslationString("pipeman.error.length_between", "Length must be between %(min) and %(max)")
            ))
        elif min_val is not None:
            validators.append(wtfv.Length(
                min=min_val,
                message=DelayedTranslationString("pipeman.error.length_less_than_min", "Length must be greater than %(min)")
            ))
        elif max_val is not None:
            validators.append(wtfv.Length(
                max=max_val,
                message=DelayedTranslationString("pipeman.error.length_greater_than_max", "Length must be less than %(max)")
            ))
        return validators


class NumberValidationMixin:

    def validators(self):
        validators = super().validators()
        min_val = self.config("min", default=None)
        max_val = self.config("max", default=None)
        if min_val is not None and max_val is not None:
            validators.append(wtfv.NumberRange(
                min=min_val,
                max=max_val,
                message=DelayedTranslationString("pipeman.error.range_between",
                                                 "Number must be between %(min) and %(max)")
            ))
        elif min_val is not None:
            validators.append(wtfv.NumberRange(
                min=min_val,
                message=DelayedTranslationString("pipeman.error.range_less_than_min",
                                                 "Number must be greater than %(min)")
            ))
        elif max_val is not None:
            validators.append(wtfv.NumberRange(
                max=max_val,
                message=DelayedTranslationString("pipeman.error.range_greater_than_max",
                                                 "Number must be less than %(max)")
            ))
        return validators

