import typing as t
import decimal
import json
import datetime

import wtforms as wtf
from autoinject import injector
import flask
import markupsafe

import pipeman.db.orm as orm
from pipeman.i18n import gettext, format_date, format_datetime
from pipeman.i18n import MultiLanguageString, DelayedTranslationString, MultiLanguageLink
from pipeman.db import Database
from pipeman.util.flask import HtmlField, FlatPickrWidget, Select2Widget
from pipeman.entity.base import Field, NumberValidationMixin, NoControlMixin, LengthValidationMixin
from pipeman.entity.keywords import Keyword


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

    def _handle_raw(self, raw_value):
        return not not raw_value


class DateField(Field):

    DATA_TYPE = "date"

    def __init__(self, *args, default_format="%Y-%m-%d", with_cal=True, with_time=False, **kwargs):
        super().__init__(*args, **kwargs)
        if "storage_format" not in self.field_config:
            self.field_config["storage_format"] = default_format
        self.with_time = with_time
        self.with_cal = with_cal

    def _control_class(self) -> t.Callable:
        return wtf.DateField

    def _extra_wtf_arguments(self) -> dict:
        return {
            "format": self.config("storage_format"),
            "widget": FlatPickrWidget(
                with_time=self.with_time,
                with_calendar=self.with_cal,
                placeholder=DelayedTranslationString("pipeman.common.placeholder")
            )
        }

    def _format_for_ui(self, val):
        return format_date(val)

    def _handle_raw(self, raw_value):
        if isinstance(raw_value, str):
            if self.with_time:
                return datetime.datetime.fromisoformat(raw_value)
            else:
                return datetime.date.fromisoformat(raw_value)
        else:
            return raw_value

    def _serialize(self, val):
        if val is None:
            return ""
        if not isinstance(val, str):
            return val.strftime(self.config("storage_format"))
        return val

    def _unserialize(self, val):
        if val is None or val == "":
            return None
        return datetime.datetime.strptime(val, self.config("storage_format"))


class DateTimeField(DateField):

    DATA_TYPE = "datetime"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, default_format="%Y-%m-%d %H:%M:%S", with_time=True)

    def _format_for_ui(self, val):
        return format_datetime(val)


class DecimalField(NumberValidationMixin, Field):

    DATA_TYPE = "decimal"

    def _control_class(self) -> t.Callable:
        return wtf.DecimalField

    def _extra_wtf_arguments(self) -> dict:
        args = {}
        if "places" in self.field_config:
            args["places"] = self.field_config["places"]
        if "rounding" in self.field_config and self.field_config["rounding"].startswith("ROUND_") and hasattr(decimal, self.field_config["rounding"]):
            args["rounding"] = getattr(decimal, self.field_config["rounding"])
        return args

    def _handle_raw(self, raw_value):
        if isinstance(raw_value, str):
            if raw_value == "":
                return None
            return decimal.Decimal(raw_value)
        if raw_value is None or isinstance(raw_value, decimal.Decimal):
            return raw_value
        return None

    def _unserialize(self, val):
        if val is None or val == "":
            return None
        return decimal.Decimal(val)

    def _serialize(self, val):
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


class ChoiceField(Field):

    DATA_TYPE = "choice"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._values = None
        self._use_default_repeatable = False

    def _control_class(self) -> t.Callable:
        return wtf.SelectMultipleField if "repeatable" in self.field_config and self.field_config["repeatable"] else wtf.SelectField

    def _extra_wtf_arguments(self) -> dict:
        from pipeman.entity import Entity
        args = {
            "choices": self.choices,
            "coerce": str,
            "widget": Select2Widget(
                allow_multiple=self.is_repeatable(),
                placeholder=DelayedTranslationString("pipeman.common.placeholder")
            ) if self.allow_javascript_controls() else None
        }
        if "coerce" in self.field_config and self.field_config["coerce"] == "int":
            args["coerce"] = int
        return args

    def _value_to_keyword(self, value):
        return Keyword(
            value,
            value,
            self._get_display_text(value),
            self.build_thesaurus(),
            self.keyword_mode()
        )

    def _update_from_keyword(self, keyword: str, keyword_dictionary: str) -> bool:
        if self.is_repeatable():
            values = self.value
            values.append(keyword)
            self.set_from_raw(list(set(values)))
        else:
            self.set_from_raw(keyword)
        return True

    def _find_choice(self, value) -> tuple:
        if value is None or value == "":
            return None, None
        for short, long in self.choices():
            if short == value:
                return short, long
        return None, None

    def _get_display_text(self, value):
        short, long = self._find_choice(value)
        return long

    def _handle_raw(self, raw_value):
        short, long = self._find_choice(raw_value)
        return short

    def choices(self):
        if self._values is None:
            self._values = self._build_choices()
        return self._values

    def _build_choices(self) -> list[tuple[str, str]]:
        v = [("", DelayedTranslationString("pipeman.common.placeholder"))]
        for x in self.field_config["values"]:
            disp = self.field_config["values"][x]
            if isinstance(disp, dict):
                v.append((x, MultiLanguageString(disp)))
            else:
                v.append((x, disp))
        return v

    def sanitize_form_input(self, val):
        if self.is_repeatable() and isinstance(val, list) and len(val) == 1 and isinstance(val[0], list):
            return val[0]
        return val

    def _format_for_ui(self, val):
        short, long = self._find_choice(val)
        if long is None:
            return ""
        return long

    def _process_value(self, val, use_label = False, **kwargs):
        short, long = self._find_choice(val)
        return long


class TextField(NoControlMixin, LengthValidationMixin, Field):

    DATA_TYPE = "text"

    def _control_class(self) -> t.Callable:
        return wtf.StringField

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

    def _process_value(self, val, none_as_blank=True, **kwargs):
        if val == "" or val is None:
            return None
        return val


class KeyValueField(Field):

    # TODO: csrf_token is getting appended to some fields, we can get rid of them?

    DATA_TYPE = "key_value"

    def _control_class(self):
        return wtf.FormField

    def _extra_wtf_arguments(self) -> dict:
        return {
            "form_class": KeyValueForm
        }

    def _handle_raw(self, raw_value):
        raise NotImplementedError("KeyValue field not implemented yet")

    def validators(self) -> list:
        return []

    def _process_value(self, val, none_as_blank=True, **kwargs):
        if not val:
            return "" if none_as_blank else None
        return val["key"], self._process_input_value(val["value"], val["data_type"])

    def _format_for_ui(self, val):
        kv = self._process_value(val)
        if kv is None or kv == "":
            return None
        return f"{kv[0]} = {kv[1]}"

    def _process_input_value(self, val, dtype):
        try:
            if dtype == 'str':
                return str(val)
            elif dtype == 'numeric':
                return float(val) if '.' in val else int(val)
            elif dtype == 'numeric_list':
                return [float(v.strip()) if '.' in v else int(v.strip()) for v in val.split(",") if v.strip()]
            else:
                self._log.error(f"Datatype not recognized {dtype} - {self.parent_type}.{self.parent_id}.{self.field_name}")
                return "?data type not recognized?"
        except (ValueError, TypeError) as ex:
            self._log.exception(f"Error parsing KeyValue field value {self.parent_type}.{self.parent_id}.{self.field_name}")
            return "?parse error?"


class MultiLineTextField(TextField):

    DATA_TYPE = "multitext"

    def _control_class(self) -> t.Callable:
        return wtf.TextAreaField

    def _format_for_ui(self, val):
        if val is None:
            return ""
        return markupsafe.Markup(val.replace("\n", '<br />'))


class TelephoneField(NoControlMixin, Field):

    DATA_TYPE = "telephone"

    def _control_class(self) -> t.Callable:
        return wtf.TelField


class TimeField(DateField):

    DATA_TYPE = "time"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, default_format="%H:%M", with_cal=False, with_time=True)

    def _control_class(self) -> t.Callable:
        return wtf.TimeField

    def _extra_wtf_arguments(self) -> dict:
        return {
            "format": self.field_config["storage_format"]
        }


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

    def _build_choices(self):
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


class VocabularyReferenceField(ChoiceField):

    DATA_TYPE = "vocabulary"

    db: Database = None

    @injector.construct
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _format_for_ui(self, val):
        if val is None or val == "":
            return ""
        txt = self._get_display_text(val)
        link = flask.url_for("core.vocabulary_term_list", vocab_name=self.field_config["vocabulary_name"], _anchor=val)
        return MultiLanguageLink(link, txt, new_tab=True)

    def label(self) -> t.Union[str, MultiLanguageString]:
        txt = self.field_config["label"] if "label" in self.field_config else ""
        link = flask.url_for("core.vocabulary_term_list", vocab_name=self.field_config["vocabulary_name"])
        if isinstance(txt, dict):
            return MultiLanguageLink(link, txt, new_tab=True)
        return MultiLanguageLink(link, {"und": txt}, new_tab=True)

    def _build_choices(self):
        values = [("", DelayedTranslationString("pipeman.common.placeholder"))]
        with self.db as session:
            for term in session.query(orm.VocabularyTerm).filter_by(vocabulary_name=self.field_config['vocabulary_name']):
                dns = json.loads(term.display_names)
                dns['und'] = term.short_name
                values.append((term.short_name, MultiLanguageString(dns)))
        return values

    def _process_value(self, val, none_as_blank=False, **kwargs):
        short, long = self._find_choice(val)
        if short is not None:
            return VocabularyTerm(short, long)
        elif none_as_blank:
            return VocabularyTerm()
        else:
            return None


class KeyValueForm(wtf.Form):

    key = wtf.StringField(
        gettext("pipeman.labels.kv_field.key")
    )

    value = wtf.TextAreaField(
        gettext("pipeman.labels.kv_field.value")
    )

    data_type = wtf.SelectField(
        gettext("pipeman.labels.kv_field.data_type"),
        choices=[
            ("str", gettext("pipeman.labels.kv_field.data_type.str")),
            ("numeric", gettext("pipeman.labels.kv_field.data_type.numeric")),
            ("numeric_list", gettext("pipeman.labels.kv_field.data_type.numeric_list")),
        ],
        default="str"
    )



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
