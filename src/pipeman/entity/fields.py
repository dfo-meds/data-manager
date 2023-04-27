import typing as t
import decimal
import wtforms as wtf
import wtforms.validators as wtfv
from pipeman.i18n import MultiLanguageString, DelayedTranslationString, MultiLanguageLink
from pipeman.db import Database
from autoinject import injector
from pipeman.util.flask import TranslatableField, HtmlField, FlatPickrWidget, Select2Widget, NoControlCharacters
import json
import pipeman.db.orm as orm
from pipeman.i18n import gettext, format_date, format_datetime
import markupsafe
import flask
import datetime


class HtmlList:

    def __init__(self, items):
        self.items = items

    def __str__(self):
        h = '<ul>'
        h += ''.join(f'<li>{item}</li>' for item in self.items if item)
        h += '</ul>'
        return markupsafe.Markup(h)


class Field:

    def __init__(self, field_name, field_config, parent_type=None, parent_id=None):
        self.field_name = field_name
        self.field_config = field_config
        self.display_group = field_config['display_group'] if 'display_group' in field_config else ""
        self.order = field_config['order'] if 'order' in field_config else 0
        self.value = None
        self._use_default_repeatable = True
        self.parent_id = parent_id
        self.parent_type = parent_type
        self._default_thesaurus = None

    def config(self, *keys, default=None):
        working = self.field_config
        for k in keys:
            if not (isinstance(working, dict) and k in working):
                return default
            working = working[k]
        return working

    def sanitize_form_input(self, val):
        return val

    def is_multilingual(self):
        return self.config("multilingual", default=False)

    def is_repeatable(self):
        return self.config("repeatable", default=False)

    def is_empty(self):
        if self.value is None or self.value == "" or self.value == []:
            return True
        if self.is_repeatable():
            for val in self.value:
                if self.is_multilingual():
                    if any(bool(val[x]) for x in val):
                        return False
                elif bool(val):
                    return False
            return True
        elif self.is_multilingual():
            return not any(bool(self.value[x]) for x in self.value)
        else:
            return not bool(self.value)

    def serialize(self, val):
        return self._unserialize(val)

    def unserialize(self, val):
        if self.is_repeatable() and not isinstance(val, list):
            return [self._unserialize(val)]
        elif (not self.is_repeatable()) and isinstance(val, list):
            return self._unserialize(val[0])
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
                keywords.append(self._value_to_keyword(value))
            return keywords
        else:
            return [self._value_to_keyword(self.value)]

    def _value_to_keyword(self, value):
        return Keyword(str(value), str(value), None, self.build_thesaurus())

    def control(self) -> wtf.Field:
        ctl_class = self._control_class()
        parent_args, field_args = self._split_args()
        use_multilingual = self.is_multilingual()
        use_repeatable = self.is_repeatable() and self._use_default_repeatable
        if use_repeatable and self.value is None:
            self.value = []
        if use_multilingual and use_repeatable:
            min_entries = max(len(self.value) if self.value else 0, 1)
            return wtf.FieldList(
                TranslatableField(ctl_class, field_kwargs=field_args, label=""),
                min_entries=min_entries,
                **parent_args
            )
        elif use_multilingual:
            return TranslatableField(ctl_class, field_kwargs=field_args, **parent_args)
        elif use_repeatable:
            min_entries = max(len(self.value) if self.value else 0, 1)
            return wtf.FieldList(ctl_class(label="", **field_args), **parent_args, min_entries=min_entries)
            pass
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
        return set(["label", "description", "default"])

    def _extra_wtf_arguments(self) -> dict:
        return {}

    def display(self):
        if self.value is None:
            return ""
        use_multilingual = self.is_multilingual()
        use_repeatable = self.is_repeatable()
        if use_repeatable and use_multilingual:
            items = [
                MultiLanguageString({
                    y: self._format_for_ui(x[y])
                    for y in x
                })
                for x in self.value
            ]
            return str(HtmlList(items))
        elif use_repeatable:
            items = [self._format_for_ui(x) for x in self.value]
            return str(HtmlList(items))
        elif use_multilingual:
            if isinstance(self.value, str):
                return MultiLanguageString({"und": self.value})
            return MultiLanguageString({
                x: self._format_for_ui(self.value[x]) for x in self.value
            })
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
        max_val = self.config("min", default=None)
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
        max_val = self.config("min", default=None)
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


class BooleanField(Field):

    DATA_TYPE = "boolean"

    def _control_class(self) -> t.Callable:
        return wtf.BooleanField

    def _format_for_ui(self, val):
        if val is None:
            return gettext("pipeman.common.na")
        elif not val:
            return gettext("pipeman.common.no")
        else:
            return gettext("pipeman.common.yes")


class DateField(Field):

    DATA_TYPE = "date"

    def __init__(self, *args, default_format="%Y-%m-%d", with_cal=True, with_time=False, **kwargs):
        super().__init__(*args, **kwargs)
        if "storage_format" not in self.field_config:
            self.field_config["storage_format"] = default_format
        self.with_time = with_time
        self.with_cal = with_cal

    def serialize(self, val):
        if val is None:
            return ""
        if not isinstance(val, str):
            return val.strftime(self.config("storage_format"))
        return val

    def unserialize(self, val):
        if val is None or val == "":
            return None
        return datetime.datetime.strptime(val, self.config("storage_format"))

    def _extra_wtf_arguments(self) -> dict:
        return {
            "format": self.config("storage_format"),
            "widget": FlatPickrWidget(
                with_time=self.with_time,
                with_calendar=self.with_cal,
                placeholder=DelayedTranslationString("pipeman.common.placeholder")
            )
        }

    def _control_class(self) -> t.Callable:
        return wtf.DateField

    def _format_for_ui(self, val):
        return format_date(val)


class DateTimeField(DateField):

    DATA_TYPE = "datetime"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, default_format="%Y-%m-%d %H:%M:%S", with_time=True)

    def _format_for_ui(self, val):
        return format_datetime(val)


class DecimalField(NumberValidationMixin, Field):

    DATA_TYPE = "decimal"

    def _extra_wtf_arguments(self) -> dict:
        args = {}
        if "places" in self.field_config:
            args["places"] = self.field_config["places"]
        if "rounding" in self.field_config and self.field_config["rounding"].startswith("ROUND_") and hasattr(decimal, self.field_config["rounding"]):
            args["rounding"] = getattr(decimal, self.field_config["rounding"])
        return args

    def _control_class(self) -> t.Callable:
        return wtf.DecimalField

    def unserialize(self, val):
        if val is None or val == "":
            return None
        return decimal.Decimal(val)

    def serialize(self, val):
        if val is None or val == "":
            return None
        return str(val)


class EmailField(NoControlMixin, LengthValidationMixin, Field):

    DATA_TYPE = "email"

    def _control_class(self) -> t.Callable:
        return wtf.EmailField


class FloatField(NumberValidationMixin, Field):

    DATA_TYPE = "float"

    def _control_class(self) -> t.Callable:
        return wtf.FloatField


class IntegerField(NumberValidationMixin, Field):

    DATA_TYPE = "integer"

    def _control_class(self) -> t.Callable:
        return wtf.IntegerField


class Keyword:

    def __init__(self, identifier, machine_key=None, translated_values=None, thesaurus=None, mode=None):
        self._identifier = identifier
        self.machine_key = machine_key
        self.translations = translated_values or {}
        self.thesaurus = thesaurus
        self.mode = mode or "value"

    def __str__(self):
        dns = self.translations.copy()
        if self.machine_key:
            dns["und"] = self.machine_key
        return str(MultiLanguageString(dns))

    def use_machine_key(self):
        return self.machine_key and self.mode == "both"

    def use_value_only(self):
        return self.machine_key and self.mode == "value"

    def to_display(self, primary_locale):
        # Only use translations
        display_dict = {
            "primary": None,
            "secondary": {}
        }
        if self.mode == "translate":
            if isinstance(self.translations, str):
                display_dict["primary"] = self.translations
            else:
                if primary_locale in self.translations:
                    display_dict["primary"] = self.translations[primary_locale]
                elif "und" in self.translations:
                    display_dict["primary"] = self.translations["und"]
                display_dict["secondary"] = {
                    key: self.translations[key]
                    for key in self.translations
                    if key != "und" and key != primary_locale and self.translations[key]
                }

        # Only use the machine key
        elif self.mode == "value":
            display_dict["primary"] = self.machine_key

        # Use a mix of both (machine key as undefined value)
        else:
            display_dict["primary"] = self.machine_key
            display_dict["secondary"] = {
                key: self.translations[key]
                for key in self.translations
                if key != "und" and self.translations[key]
            }
        return display_dict

    def key_identifier(self):
        if self._identifier:
            return self._identifier
        if self.machine_key:
            return self.machine_key

    def thesaurus_group(self):
        if not self.thesaurus:
            return ''
        if 'citation' not in self.thesaurus:
            return ''
        if not self.thesaurus['citation']:
            return ''
        if 'title' not in self.thesaurus['citation']:
            return ''
        if not self.thesaurus['citation']['title']:
            return ''
        if isinstance(self.thesaurus['citation']['title'], str):
            return self.thesaurus['citation']['title']
        keys = ['en', 'und']
        keys.extend(self.thesaurus['citation']['title'].keys())
        for key in keys:
            if key in self.thesaurus['citation']['title'] and self.thesaurus['citation']['title'][key]:
                return self.thesaurus['citation']['title'][key]
        return ''


class KeywordGroup:

    def __init__(self, thesaurus):
        self.thesaurus = thesaurus
        self._keywords = {}

    def append(self, keyword: Keyword):
        self._keywords[keyword.key_identifier()] = keyword

    def keywords(self):
        key_names = list(self._keywords.keys())
        key_names.sort()
        for name in key_names:
            yield self._keywords[name]


class ChoiceField(Field):

    DATA_TYPE = "choice"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._values = None
        self._use_default_repeatable = False

    def _value_to_keyword(self, value):
        return Keyword(
            value,
            value,
            self._get_display_text(value),
            self.build_thesaurus(),
            self.keyword_mode()
        )

    def _get_display_text(self, value):
        return self.field_config["values"][value]

    def choices(self):
        if self._values is None:
            self._values = [("", DelayedTranslationString("pipeman.common.placeholder"))]
            for x in self.field_config["values"]:
                disp = self.field_config["values"][x]
                if isinstance(disp, dict):
                    self._values.append((x, MultiLanguageString(disp)))
                else:
                    self._values.append((x, disp))
        return self._values

    def sanitize_form_input(self, val):
        if self.is_repeatable() and isinstance(val, list) and len(val) == 1 and isinstance(val[0], list):
            return val[0]
        return val

    def filters(self) -> list:
        filts = super().filters()
        #filts.append(text_sanitize)
        return filts

    def _extra_wtf_arguments(self) -> dict:
        args = {
            "choices": self.choices,
            "coerce": str,
            "widget": Select2Widget(
                allow_multiple=self.is_repeatable(),
                placeholder=DelayedTranslationString("pipeman.common.placeholder")
            )
        }
        if "coerce" in self.field_config and self.field_config["coerce"] == "int":
            args["coerce"] = int
        return args

    def _control_class(self) -> t.Callable:
        return wtf.SelectMultipleField if "repeatable" in self.field_config and self.field_config["repeatable"] else wtf.SelectField

    def _format_for_ui(self, val):
        if val is None or val == "":
            return ""
        lst = self.choices()
        for key, disp in lst:
            if key == val:
                return disp
        return gettext("pipeman.common.unknown")

    def _process_value(self, val, **kwargs):
        if val is None:
            return None
        if "use_label" in kwargs and kwargs["use_label"]:
            choices = self.choices()
            if val in choices:
                return choices[val]
        return val


class TextField(NoControlMixin, LengthValidationMixin, Field):

    DATA_TYPE = "text"

    def _unserialize(self, val):
        if self.is_multilingual() and not isinstance(val, dict):
            return {"und": val}
        elif (not self.is_multilingual()) and isinstance(val, dict):
            if "und" in val and val["und"]:
                return val["und"]
            elif "en" in val and val["en"]:
                return val["en"]
            else:
                for key in val:
                    if val[key]:
                        return val[key]
                return None
        return val if not val == "" else None

    def _control_class(self) -> t.Callable:
        return wtf.StringField

    def _process_value(self, val, none_as_blank=True, **kwargs):
        if val == "" or val is None:
            return None
        return val


class MultiLineTextField(TextField):

    DATA_TYPE = "multitext"

    def _control_class(self) -> t.Callable:
        return wtf.TextAreaField


class TelephoneField(NoControlMixin, Field):

    DATA_TYPE = "telephone"

    def filters(self) -> list:
        filts = super().filters()
        #filts.append(text_sanitize)
        return filts

    def _control_class(self) -> t.Callable:
        return wtf.TelField


class TimeField(DateField):

    DATA_TYPE = "time"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, default_format="%H:%M", with_cal=False, with_time=True)

    def _extra_wtf_arguments(self) -> dict:
        return {
            "format": self.field_config["storage_format"]
        }

    def _control_class(self) -> t.Callable:
        return wtf.TimeField


class URLField(NoControlMixin, LengthValidationMixin, Field):

    DATA_TYPE = "url"

    def _control_class(self) -> t.Callable:
        return wtf.URLField


class DatasetReferenceField(ChoiceField):

    DATA_TYPE = "dataset_ref"

    db: Database = None

    @injector.construct
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._value_cache = None

    def choices(self):
        if self._value_cache is None:
            self._value_cache = self._load_values()
        return self._value_cache

    def _load_values(self):
        values = [("", DelayedTranslationString("pipeman.common.placeholder"))]
        with self.db as session:
            for entity in session.query(orm.Dataset).filter_by(is_deprecated=False):
                values.append((entity.id, MultiLanguageString(json.loads(entity.display_names) if entity.display_names else {})))
        return values


class HtmlContentField(Field):

    def control(self):
        parent_args, field_args = self._split_args()
        return HtmlField(**parent_args, **field_args)

    def _control_class(self):
        return None

    def _extra_wtf_arguments(self) -> dict:
        return {
            "html_content": self._build_html_content()
        }

    def _build_html_content(self):
        raise NotImplementedError()


class VocabularyTerm:

    def __init__(self, term_key=None, term_label=None):
        self._short_name = term_key
        self._display = term_label

    def __bool__(self):
        return self._short_name is not None

    def short_name(self):
        return self._short_name

    def display(self):
        return MultiLanguageString(json.loads(self._display)) if self._display else ""

    def __getitem__(self, key):
        if key == "short_name":
            return self.short_name()
        if key == "display":
            return self.display()


class VocabularyReferenceField(ChoiceField):

    DATA_TYPE = "vocabulary"

    db: Database = None

    @injector.construct
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._value_cache = None

    def _get_display_text(self, value):
        with self.db as session:
            term = session.query(orm.VocabularyTerm).filter_by(
                vocabulary_name=self.field_config["vocabulary_name"],
                short_name=value
            ).first()
            if term and term.display_names:
                return json.loads(term.display_names)
        return {}

    def label(self) -> t.Union[str, MultiLanguageString]:
        txt = self.field_config["label"] if "label" in self.field_config else ""
        link = flask.url_for("core.vocabulary_term_list", vocab_name=self.field_config["vocabulary_name"])
        if isinstance(txt, dict):
            return MultiLanguageLink(link, txt, new_tab=True)
        return MultiLanguageLink(link, {"und": txt}, new_tab=True)

    def choices(self):
        if self._value_cache is None:
            self._value_cache = self._load_values()
        return self._value_cache

    def _load_values(self):
        values = [("", DelayedTranslationString("pipeman.common.placeholder"))]
        with self.db as session:
            for term in session.query(orm.VocabularyTerm).filter_by(vocabulary_name=self.field_config['vocabulary_name']):
                dns = json.loads(term.display_names)
                dns['und'] = term.short_name
                values.append((term.short_name, MultiLanguageString(dns)))
        return values

    def _process_value(self, val, none_as_blank=False, **kwargs):
        with self.db as session:
            term = session.query(orm.VocabularyTerm).filter_by(vocabulary_name=self.field_config["vocabulary_name"], short_name=val).first()
            if term is not None:
                return VocabularyTerm(term.short_name, term.display_names)
        return VocabularyTerm()
