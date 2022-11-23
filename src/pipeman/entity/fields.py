import typing as t
import decimal
import wtforms as wtf
import wtforms.validators as wtfv
from pipeman.i18n import MultiLanguageString, DelayedTranslationString
from pipeman.db import Database
from autoinject import injector
from pipeman.util.flask import TranslatableField
import json
import pipeman.db.orm as orm
from pipeman.vocab import VocabularyTermController


class Field:

    def __init__(self, field_name, field_config):
        self.field_name = field_name
        self.field_config = field_config
        self.value = None
        self._use_default_repeatable = True

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

    def _control(self) -> wtf.Field:
        return wtf.BooleanField(**self._wtf_arguments())


class DateField(Field):

    DATA_TYPE = "date"

    def __init__(self, field_name, field_config, default_format="%Y-%m-%d"):
        super().__init__(field_name, field_config)
        if "storage_format" not in self.field_config:
            self.field_config["storage_format"] = default_format

    def _extra_wtf_arguments(self) -> dict:
        return {
            "format": self.field_config["storage_format"]
        }

    def _control_class(self) -> t.Callable:
        return wtf.DateField


class DateTimeField(DateField):

    DATA_TYPE = "datetime"

    def __init__(self, field_name, field_config):
        super().__init__(field_name, field_config, "%Y-%m-%d %H:%M:%S")

    def _control_class(self) -> t.Callable:
        return wtf.DateTimeField


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

    def choices(self):
        values = [("", DelayedTranslationString("pipeman.empty_select"))]
        values.extend([(x, self.field_config["values"][x]) for x in self.field_config["values"]])
        return values

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


class TimeField(Field):

    DATA_TYPE = "time"

    def __init__(self, field_name, field_config):
        super().__init__(field_name, field_config)
        if "storage_format" not in self.field_config:
            self.field_config["storage_format"] = "%H:%M"

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


class EntityReferenceField(ChoiceField):

    DATA_TYPE = "entity_ref"

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
        values = [("", DelayedTranslationString("pipeman.empty_select"))]
        with self.db as session:
            for entity in session.query(orm.Entity).filter_by(entity_type=self.field_config['entity_type']):
                values.append((entity.id, MultiLanguageString(json.loads(entity.display_names))))
        return values


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
        values = [("", DelayedTranslationString("pipeman.empty_select"))]
        with self.db as session:
            for term in session.query(orm.VocabularyTerm).filter_by(vocabulary_name=self.field_config['vocabulary_name']):
                values.append((term.short_name, MultiLanguageString(json.loads(term.display_names))))
        return values