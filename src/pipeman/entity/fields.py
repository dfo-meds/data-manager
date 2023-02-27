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

    def __init__(self, field_name, field_config, parent_type=None, parent_id=None):
        self.field_name = field_name
        self.field_config = field_config
        self.display_group = field_config['display_group'] if 'display_group' in field_config else ""
        self.order = field_config['order'] if 'order' in field_config else 0
        self.value = None
        self._use_default_repeatable = True
        self.parent_id = parent_id
        self.parent_type = parent_type

    def sanitize_form_input(self, val):
        return val

    def is_multilingual(self):
        return "multilingual" in self.field_config and self.field_config["multilingual"]

    def is_repeatable(self):
        return "repeatable" in self.field_config and self.field_config["repeatable"]

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

    def get_keywords(self, language):
        if not self.value:
            return set()
        if "keyword_config" not in self.field_config:
            return set()
        if "is_keyword" not in self.field_config["keyword_config"] or not self.field_config["keyword_config"]["is_keyword"]:
            return set()
        default_thesaurus = None
        thesaurus_field = None
        extraction_method = "value"
        if "thesaurus" in self.field_config["keyword_config"]:
            default_thesaurus = self.field_config['keyword_config']['thesaurus']
        if "thesaurus_field" in self.field_config["keyword_config"]:
            thesaurus_field = self.field_config["keyword_config"]["thesaurus_field"]
        if "extraction_method" in self.field_config["keyword_config"]:
            extraction_method = self.field_config["keyword_config"]["extraction_method"]
        return self._extract_keywords(language, default_thesaurus, thesaurus_field=thesaurus_field, extraction_method=extraction_method)

    def _extract_keywords(self, language, default_thesaurus, **kwargs):
        if self.is_repeatable():
            keywords = []
            for value in self.value:
                keywords.extend(self._as_keyword(value, language, default_thesaurus, **kwargs))
            return keywords
        else:
            return self._as_keyword(self.value, language, default_thesaurus, **kwargs)

    def _as_keyword(self, value, language, default_thesaurus, **kwargs):
        return [(str(value), "und", default_thesaurus),]

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

    def __init__(self, field_name, field_config, container_type, container_id, default_format="%Y-%m-%d"):
        super().__init__(field_name, field_config, container_type, container_id)
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

    def __init__(self, field_name, field_config, container_type, container_id):
        super().__init__(field_name, field_config, container_type, container_id, "%Y-%m-%d %H:%M:%S")

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

    def unserialize(self, val):
        if val is None or val == "":
            return None
        return decimal.Decimal(val)

    def serialize(self, val):
        if val is None or val == "":
            return None
        return str(val)


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

    def _as_keyword(self, value, language, default_thesaurus, extraction_method, **kwargs):
        if extraction_method == "translated":
            disp = self._get_display(value)
            if isinstance(disp, dict):
                if language == "*":
                    keys = [disp.keys()]
                    omit_und = len(keys) > 1 or keys[0] != "und"
                    keywords = []
                    for key in disp:
                        if omit_und and key == "und":
                            continue
                        keywords.append((disp[key], key, default_thesaurus))
                    return keywords
                elif language in disp:
                    return [(disp[language], language, default_thesaurus), ]
                elif "und" in disp:
                    return [(disp["und"], "und", default_thesaurus), ]
                else:
                    return []
            else:
                return [(disp, "und", default_thesaurus), ]
        else:
            return [(value, "und", default_thesaurus), ]

    def _get_display(self, value):
        return self.field_config["values"][value]

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

    def sanitize_form_input(self, val):
        if self.is_repeatable() and isinstance(val, list) and len(val) == 1 and isinstance(val[0], list):
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
                return ""
        return val

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

    def __init__(self, field_name, field_config, container_type, container_id):
        super().__init__(field_name, field_config, container_type, container_id, default_format="%H:%M")

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

    def _get_display(self, value):
        with self.db as session:
            term = session.query(orm.VocabularyTerm).filter_by(vocabulary_name=self.field_config['vocabulary_name'], short_name=value).first()
            if term:
                dns = json.loads(term.display_names)
                dns['und'] = value
                return dns

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

    def _process_value(self, val, none_as_blank=False, **kwargs):
        with self.db as session:
            term = session.query(orm.VocabularyTerm).filter_by(vocabulary_name=self.field_config["vocabulary_name"], short_name=val).first()
            if term is not None:
                return VocabularyTerm(term.short_name, term.display_names)
        return VocabularyTerm()
