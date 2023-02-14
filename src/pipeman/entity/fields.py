import typing as t
import decimal
import wtforms as wtf
import wtforms.validators as wtfv
from pipeman.i18n import MultiLanguageString, DelayedTranslationString
from pipeman.db import Database
from autoinject import injector
from pipeman.util.flask import TranslatableField, HtmlField
import json
import pipeman.db.orm as orm
from pipeman.i18n import gettext, format_date, format_datetime
import markupsafe
import datetime


class HtmlList:

    def __init__(self, items):
        self.items = items

    def __str__(self):
        h = '<ul>'
        h += ''.join(f'<li>{item}</li>' for item in self.items)
        h += '</ul>'
        return markupsafe.Markup(h)


class Field:

    def __init__(self, field_name, field_config, parent_id=None):
        self.field_name = field_name
        self.field_config = field_config
        self.display_group = field_config['display_group'] if 'display_group' in field_config else ""
        self.order = field_config['order'] if 'order' in field_config else 0
        self.value = None
        self._use_default_repeatable = True
        self.parent_id = parent_id

    def cleanup_value(self, val):
        return val

    def serialize(self, val):
        return val

    def unserialize(self, val):
        return val

    def control(self) -> wtf.Field:
        ctl_class = self._control_class()
        parent_args, field_args = self._split_args()
        use_multilingual = "multilingual" in self.field_config and self.field_config["multilingual"]
        use_repeatable = "repeatable" in self.field_config and self.field_config["repeatable"] and self._use_default_repeatable
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

    def label(self) -> t.Union[str, MultiLanguageString]:
        txt = self.field_config["label"] if "label" in self.field_config else ""
        if isinstance(txt, dict):
            return MultiLanguageString(txt)
        return txt

    def description(self) -> t.Union[str, MultiLanguageString]:
        txt = self.field_config["description"] if "description" in self.field_config else ""
        if isinstance(txt, dict):
            return MultiLanguageString(txt)
        return txt

    def validators(self) -> list:
        validators = []
        if "is_required" in self.field_config and self.field_config["is_required"]:
            validators.append(wtfv.InputRequired())
        else:
            validators.append(wtfv.Optional())
        return validators

    def default_value(self) -> t.Any:
        return self.value

    def _wtf_arguments(self) -> dict:
        print(self.field_name)
        print(self.label())
        args = {
            "label": self.label(),
            "description": self.description(),
            "validators": self.validators(),
            "default": self.default_value
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
        use_multilingual = "multilingual" in self.field_config and self.field_config["multilingual"]
        use_repeatable = "repeatable" in self.field_config and self.field_config["repeatable"]
        if use_repeatable and use_multilingual:
            items = [
                MultiLanguageString({
                    y: self._format_for_ui(self.value[x][y])
                    for y in x
                })
                for x in self.value
            ]
            return str(HtmlList(items))
        elif use_repeatable:
            items = [self._format_for_ui(x) for x in self.value]
            return str(HtmlList(items))
        elif use_multilingual:
            return MultiLanguageString({
                x: self._format_for_ui(self.value[x]) for x in self.value
            })
        else:
            return self._format_for_ui(self.value)

    def data(self, lang=None, index=None, **kwargs):
        use_multilingual = "multilingual" in self.field_config and self.field_config["multilingual"]
        use_repeatable = "repeatable" in self.field_config and self.field_config["repeatable"]
        value = self.value
        if index is not None and use_repeatable:
            if index >= len(self.value):
                return None
            value = self.value[index]
            use_repeatable = False
        if lang is not None and use_multilingual:
            value = self.value[lang]
            use_multilingual = False
        if use_repeatable and use_multilingual:
            return [
                {
                    y: self._process_value(value[x][y], **kwargs)
                    for y in x
                }
                for x in value
            ]
        elif use_repeatable:
            return [self._process_value(x, **kwargs) for x in value]
        elif use_multilingual:
            return {
                x: self._process_value(value[x], **kwargs) for x in value
            }
        else:
            return self._process_value(value, **kwargs)

    def _process_value(self, val, **kwargs):
        return val

    def _format_for_ui(self, val):
        if val is None:
            return ""
        return str(val)


class LengthValidationMixin:

    def validators(self):
        validators = super().validators()
        if "min" in self.field_config or "max" in self.field_config:
            args = {}
            if "min" in self.field_config:
                args["min"] = self.field_config["min"]
            if "max" in self.field_config:
                args["max"] = self.field_config["max"]
            validators.append(wtfv.Length(**args))
        return validators


class NumberValidationMixin:

    def validators(self):
        validators = super().validators()
        if "min" in self.field_config or "max" in self.field_config:
            args = {}
            if "min" in self.field_config:
                args["min"] = self.field_config["min"]
            if "max" in self.field_config:
                args["max"] = self.field_config["max"]
            validators.append(wtfv.NumberRange(**args))
        return validators


class BooleanField(Field):

    DATA_TYPE = "boolean"

    def _control_class(self) -> t.Callable:
        return wtf.BooleanField

    def _format_for_ui(self, val):
        if val is None:
            return gettext("pipeman.general.na")
        elif not val:
            return gettext("pipeman.general.no")
        else:
            return gettext("pipeman.general.yes")


class DateField(Field):

    DATA_TYPE = "date"

    def __init__(self, field_name, field_config, container_id, default_format="%Y-%m-%d"):
        super().__init__(field_name, field_config, container_id)
        if "storage_format" not in self.field_config:
            self.field_config["storage_format"] = default_format

    def serialize(self, val):
        if val is None:
            return ""
        if not isinstance(val, str):
            return val.strftime(self.field_config["storage_format"])
        return val

    def unserialize(self, val):
        if val is None or val == "":
            return None
        return datetime.datetime.strptime(val, self.field_config["storage_format"])

    def _extra_wtf_arguments(self) -> dict:
        return {
            "format": self.field_config["storage_format"]
        }

    def _control_class(self) -> t.Callable:
        return wtf.DateField

    def _format_for_ui(self, val):
        return format_date(val)


class DateTimeField(DateField):

    DATA_TYPE = "datetime"

    def __init__(self, field_name, field_config, container_id):
        super().__init__(field_name, field_config, container_id, "%Y-%m-%d %H:%M:%S")

    def _control_class(self) -> t.Callable:
        return wtf.DateTimeField

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


class EmailField(LengthValidationMixin, Field):

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


class ChoiceField(Field):

    DATA_TYPE = "choice"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._values = None
        self._use_default_repeatable = False

    def choices(self):
        if self._values is None:
            self._values = [("", DelayedTranslationString("pipeman.general.empty_select"))]
            for x in self.field_config["values"]:
                disp = self.field_config["values"][x]
                if isinstance(disp, dict):
                    self._values.append((x, MultiLanguageString(disp)))
                else:
                    self._values.append((x, disp))
        return self._values

    def cleanup_value(self, val):
        if "repeatable" not in self.field_config or not self.field_config["repeatable"]:
            return val
        if isinstance(val, list) and len(val) == 1 and isinstance(val[0], list):
            return val[0]
        return val

    def _extra_wtf_arguments(self) -> dict:
        args = {
            "choices": self.choices,
            "coerce": str
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
        return gettext("pipeman.general.unknown")

    def _process_value(self, val, **kwargs):
        if val is None:
            return None
        if "use_label" in kwargs and kwargs["use_label"]:
            choices = self.choices()
            if val in choices:
                return choices[val]
        return val


class TextField(LengthValidationMixin, Field):

    DATA_TYPE = "text"

    def _control_class(self) -> t.Callable:
        return wtf.StringField


class MultiLineTextField(TextField):

    DATA_TYPE = "multitext"

    def _control_class(self) -> t.Callable:
        return wtf.TextAreaField


class TelephoneField(Field):

    DATA_TYPE = "telephone"

    def _control_class(self) -> t.Callable:
        return wtf.TelField


class TimeField(DateField):

    DATA_TYPE = "time"

    def __init__(self, field_name, field_config, container_id):
        super().__init__(field_name, field_config, container_id, default_format="%H:%M")

    def _extra_wtf_arguments(self) -> dict:
        return {
            "format": self.field_config["storage_format"]
        }

    def _control_class(self) -> t.Callable:
        return wtf.TimeField


class URLField(LengthValidationMixin, Field):

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
        values = [("", DelayedTranslationString("pipeman.general.empty_select"))]
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


class VocabularyReferenceField(ChoiceField):

    DATA_TYPE = "vocabulary"

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
        values = [("", DelayedTranslationString("pipeman.general.empty_select"))]
        with self.db as session:
            for term in session.query(orm.VocabularyTerm).filter_by(vocabulary_name=self.field_config['vocabulary_name']):
                dns = json.loads(term.display_names)
                dns['und'] = term.short_name
                values.append((term.short_name, MultiLanguageString(dns)))
        return values

    def _process_value(self, val, **kwargs):
        with self.db as session:
            term = session.query(orm.VocabularyTerm).filter_by(vocabulary_name=self.field_config["vocabulary_name"], short_name=val).first()
            return {
                "short_name": term.short_name,
                "display": MultiLanguageString(json.loads(term.display_names))
            }
