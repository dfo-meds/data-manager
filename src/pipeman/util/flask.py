import markupsafe
import wtforms as wtf
from wtforms.form import BaseForm
from pipeman.i18n import TranslationManager, DelayedTranslationString, MultiLanguageString
from pipeman.db import Database
import pipeman.db.orm as orm
from autoinject import injector
from flask_wtf import FlaskForm
import flask
import math
import json
from markupsafe import Markup, escape
from pipeman.i18n import gettext, LanguageDetector
from pipeman.util.errors import FormValueError
import sqlalchemy as sa
import flask_login


def flash_wrap(message, category):
    flask.flash(str(message), str(category))


def get_real_remote_ip():
    remote_ip = "no request"
    if flask.has_request_context():
        if "X-Forwarded-For" in flask.request.headers:
            remote_ip = flask.request.headers.getlist("X-Forwarded-For")[0].rpartition(' ')[-1]
        else:
            remote_ip = flask.request.remote_addr or 'untrackable'
    return remote_ip


class BareHtmlWidget:

    def __call__(self, field, **kwargs):
        return field.html_content


class HtmlField(wtf.Field):

    def __init__(self, html_content=None, **kwargs):
        super().__init__(widget=BareHtmlWidget(), **kwargs)
        self.html_content = html_content
        self.data = None

    def validate(self, *args, **kwargs):
        return True

    def process(self, *args, **kwargs):
        return


class ActionList:

    def __init__(self):
        self.action_items = []

    def __bool__(self):
        return bool(self.action_items)

    def add_action(self, label_str, endpoint, **kwargs):
        self.action_items.append((
            flask.url_for(endpoint, **kwargs),
            label_str
        ))

    def render(self, html_cls="action_list"):
        mu = f'<ul class="{html_cls}">'
        for path, txt in self.action_items:
            mu += f'<li><a href="{escape(path)}">{gettext(txt)}</a></li>'
        mu += '</ul>'
        return Markup(mu)

    def __html__(self):
        return self.render()


def paginate_query(query, min_page_size=10, max_page_size=250, default_page_size=50):
    count = query.count()
    page_size = flask.request.args.get("size", "")
    if not page_size.isdigit():
        page_size = default_page_size
    else:
        page_size = int(page_size)
        if page_size > max_page_size:
            page_size = max_page_size
        elif page_size < min_page_size:
            page_size = min_page_size
    max_pages = max(1, math.ceil(count / page_size))
    page = flask.request.args.get("page", "")
    if not page.isdigit():
        page = 1
    else:
        page = int(page)
        if page > 1 and page > max_pages:
            page = max_pages
    return (
        query.limit(page_size).offset((page - 1) * page_size),
        {
            "current_page": page,
            "page_size": page_size,
            "page_count": max_pages,
            "item_count": count
        }
    )


class ConfirmationForm(FlaskForm):

    submit = wtf.SubmitField(DelayedTranslationString("pipeman.general.submit"))


class FlatPickrWidget:

    def __init__(self, placeholder=None, with_calendar=True, with_time=False):
        self.placeholder = placeholder
        self.with_calendar = bool(with_calendar)
        self.with_time = bool(with_time)

    @injector.inject
    def __call__(self, field, ld: LanguageDetector = None, tm: TranslationManager = None, **kwargs):
        markup = f'<input class="form-control-datetime-flatpickr" id="{field.id}" name="{field.name}" data-input '
        if self.placeholder:
            markup += f"placeholder='{markupsafe.escape(self.placeholder)}' "
        if field.data:
            markup += f"value='{str(field.data)}' "
        markup += '/>'
        markup += f' <button type="button" id="flatpickr-clear-button-{field.id}">{gettext("pipeman.general.clear")}</button>'
        markup += '<script language="javascript" type="text/javascript">'
        markup += '$(document).ready(function() {\n'
        markup += f"  let fp = $('#{field.id}').flatpickr(" + "{\n"
        if self.with_time:
            markup += "    'enableTime': true,\n"
            markup += "    'enableSeconds': true,\n"
            markup += "    'minuteIncrement': 1,\n"
        if not self.with_calendar:
            markup += "    'noCalendar': true,\n"
        markup += f"    'locale': '{ld.detect_language(tm.supported_languages())}'\n"
        markup += "  });\n"
        markup += f"  $('#flatpickr-clear-button-{field.id}').data('flatpickr', fp);"
        markup += f"  $('#flatpickr-clear-button-{field.id}').click(function() " + "{\n"
        markup += f"      $(this).data('flatpickr').clear();\n"
        markup += "});\n"
        markup += "});\n"
        markup += '</script>'
        return markupsafe.Markup(markup)


class Select2Widget:

    def __init__(self, ajax_callback=None, allow_multiple=False, query_delay=None, placeholder=None, min_input=None):
        self.ajax_callback = ajax_callback
        self.allow_multiple = allow_multiple
        self.query_delay = query_delay or 0
        self.placeholder = placeholder
        self.min_input = min_input

    def __call__(self, field, **kwargs):
        markup = f'<select class="form-control-select2" id="{field.id}" name="{field.name}"'
        if self.allow_multiple:
            markup += 'multiple="multiple"'
        markup += '>'
        for val, label, selected in field.iter_choices():
            markup += self.render_option(val, label, selected)
        markup += '</select><script language="javascript" type="text/javascript">'
        markup += '$(document).ready(function() {\n'
        markup += f"  $('#{field.id}').select2(" + "{\n"
        if self.ajax_callback:
            markup += "    ajax: {\n"
            markup += f"      url: '{self.ajax_callback}',\n"
            markup += "      dataType: 'json'\n"
            markup += "    },\n"
            if self.min_input:
                markup += f"    minimumInputLength: {int(self.min_input)},\n"
        if self.placeholder:
            markup += "    allowClear: true,\n"
            markup += f"    placeholder: '{self.placeholder}',\n"
        markup += f"    delay: {int(self.query_delay)}\n"
        markup += "  });\n"
        markup += "});\n"
        markup += '</script>'
        return markupsafe.Markup(markup)

    def render_option(self, val, label, selected, **kwargs):
        if val is True:
            value = str(val)
        sel_text = " selected=\"selected\"" if selected else ""
        return f'<option{sel_text}>{markupsafe.escape(label)}</option>'


class EntitySelectField(wtf.Field):

    db: Database = None

    @injector.construct
    def __init__(self, *args, entity_types, allow_multiple=False, min_chars_to_search=0, by_revision=False, widget=None, **kwargs):
        self.data = None
        self.entity_types = [entity_types] if isinstance(entity_types, str) else entity_types
        self.allow_multiple = bool(allow_multiple)
        self.include_empty = False
        self.by_revision = bool(by_revision)
        if widget is None:
            widget = Select2Widget(
                ajax_callback=flask.url_for(
                    "core.api_entity_select_field_list",
                    entity_types="|".join(self.entity_types),
                    by_revision=("1" if self.by_revision else "0"),
                    _external=True
                ),
                allow_multiple=self.allow_multiple,
                query_delay=250,
                placeholder=DelayedTranslationString("pipeman.general.empty_select"),
                min_input=min_chars_to_search
            )
        super().__init__(*args, widget=widget, **kwargs)

    @staticmethod
    @injector.inject
    def results_list(entity_types, text, by_revision, db: Database = None):
        results = {
            "results": [],
        }
        with db as session:
            q = session.query(orm.Entity)
            if isinstance(entity_types, str):
                q = q.filter_by(entity_type=entity_types)
            elif len(entity_types) == 1:
                q = q.filter_by(entity_type=entity_types[0])
            else:
                q = q.filter(orm.Entity.entity_type.in_(entity_types))
            if text:
                if "%" not in text:
                    text = f"%{text}%"
                q = q.filter(orm.Entity.display_names.ilike(text))
            if not flask_login.current_user.has_permission("organization.manage_any"):
                q = q.filter(sa.or_(
                    orm.Entity.organization_id.in_(flask_login.current_user.organizations),
                    orm.Entity.organization_id == None
                ))
            q = q.order_by(orm.Entity.id)
            for ent in q:
                results['results'].append(EntitySelectField._build_entry(ent, by_revision))
        return results

    @staticmethod
    def _build_entry(entity, by_revision, revision_no = None):
        rev = None
        if by_revision:
            rev = entity.latest_revision() if revision_no is None else entity.specific_revision(revision_no)
        return {
            "id": str(entity.id) if not by_revision else f"{entity.id}|{rev.revision_no}",
            "text": MultiLanguageString(
                json.loads(entity.display_names)
                if entity.display_names else
                {"und": f"#{entity.id}"}
            )
        }

    def iter_groups(self):
        return []

    def iter_choices(self):
        if self.include_empty:
            yield "", DelayedTranslationString("pipeman.general.empty_select"), not self.data
        if self.data:
            with self.db as session:
                if self.allow_multiple:
                    for x in self.data:
                        try:
                            ent, rev = EntitySelectField.load_entity_option(x, session, self.by_revision)
                            entry = EntitySelectField._build_entry(ent, self.by_revision, rev.revision_no if rev else None)
                            yield entry["id"], entry["text"], True
                        except FormValueError:
                            pass
                else:
                    try:
                        ent, rev = EntitySelectField.load_entity_option(self.data, session, self.by_revision)
                        entry = EntitySelectField._build_entry(ent, self.by_revision, rev.revision_no if rev else None)
                        yield entry["id"], entry["text"], True
                    except FormValueError:
                        pass

    def pre_validate(self, form):
        if self.data:
            with self.db as session:
                if self.allow_multiple:
                    for x in self.data:
                        EntitySelectField.load_entity_option(x, session, self.by_revision)
                else:
                    EntitySelectField.load_entity_option(self.data, session, self.by_revision)

    @staticmethod
    def parse_entity_option(value, by_revision):
        entity_id = value or None
        revision_no = None
        if by_revision:
            if "|" not in value:
                raise FormValueError("pipeman.entity_field.missing_revision_piece")
            pieces = value.split("|", maxsplit=1)
            if not len(pieces) == 2:
                raise FormValueError("pipeman.entity_field.malformed_revision_str")
            entity_id = pieces[0] or None
            revision_no = pieces[1] or None
        if entity_id is None:
            raise FormValueError("pipeman.entity_field_missing_entity_id")
        if not entity_id.isdigit():
            raise FormValueError("pipeman.entity_field.bad_entity_id")
        if revision_no is not None and not revision_no.isdigit():
            raise FormValueError("pipeman.entity_field.bad_revision_no")
        return int(entity_id), int(revision_no) if revision_no else None

    @staticmethod
    def load_entity_option(value, session, by_revision):
        entity_id, revision_no = EntitySelectField.parse_entity_option(value, by_revision)
        ent = session.query(orm.Entity).filter_by(id=int(entity_id)).first()
        rev = None
        if not ent:
            raise FormValueError("pipeman.entity_field.no_such_entity")
        if not flask_login.current_user.has_permission("organization.manage_any"):
            if ent.organization_id is not None and ent.organization_id not in flask_login.current_user.organizations:
                raise FormValueError("pipeman.entity_field.no_entity_access")
        if revision_no:
            rev = session.query(orm.EntityData).filter_by(entity_id=int(entity_id), revision_no=int(revision_no)).first()
            if not rev:
                raise FormValueError("pipeman.entity_field.no_such_revision")
        return ent, rev

    def process_data(self, value):
        if self.allow_multiple:
            self.data = list(str(v) for v in value) if value else []
        else:
            self.data = str(value) if value else None

    def process_formdata(self, valuelist):
        if self.allow_multiple:
            self.data = list(str(v) for v in valuelist) if valuelist else []
        else:
            self.data = str(valuelist[0]) if valuelist else None


class DynamicFormField(wtf.FormField):

    def __init__(self, fields, *args, **kwargs):
        self.field_list = fields
        super().__init__(self._generate_form, *args, **kwargs)

    def _generate_form(self, formdata=None, obj=None,  **kwargs):
        defaults = {}
        for key in self.field_list:
            if key in kwargs:
                defaults[key] = kwargs.pop(key)
        form = BaseForm(self.field_list, **kwargs)
        form.process(formdata, obj, data=defaults)
        return form


class TranslatableField(DynamicFormField):

    tm: TranslationManager = None

    @injector.construct
    def __init__(self, template_field, field_kwargs=None, *args, use_undefined=True, **kwargs):
        self.template_field = template_field
        self.use_undefined = use_undefined
        self.template_args = field_kwargs or {}
        if "label" in self.template_args:
            del self.template_args["label"]
        super().__init__(self._build_field_list(), *args, **kwargs)

    def _build_field_list(self):
        fields = {}
        if self.use_undefined:
            fields['und'] = self.template_field(label=DelayedTranslationString("languages.short.und"), **self.template_args)
        fields.update({
            lang: self.template_field(label=DelayedTranslationString(f"languages.short.{lang.lower()}"), **self.template_args)
            for lang in self.tm.supported_languages()
        })
        return fields
