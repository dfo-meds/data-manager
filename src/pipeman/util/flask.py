import markupsafe
import wtforms as wtf
from pipeman.i18n import TranslationManager, DelayedTranslationString, MultiLanguageString
from pipeman.db import Database
import pipeman.db.orm as orm
from autoinject import injector
from flask_wtf import FlaskForm
from wtforms.form import BaseForm
from wtforms.meta import DefaultMeta
from flask_wtf.csrf import _FlaskFormCSRF
import flask
import math
import json
import typing as t
from markupsafe import Markup, escape
from pipeman.i18n import gettext, LanguageDetector
from pipeman.util.errors import FormValueError
import sqlalchemy as sa
import flask_login
import zirconium as zr
import subprocess
import os
import shutil
import yaml
import datetime


@injector.injectable_global
class PathMapper:

    cfg: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self._path_map = {}
        path_map_file = self.cfg.as_path(("pipeman", "i18n_paths_file"))
        if path_map_file and path_map_file.exists():
            with open(path_map_file, "r", encoding="utf-8") as h:
                self._path_map = yaml.safe_load(h) or {}

    def get_path_translations(self, path):
        if path in self._path_map and self._path_map[path]:
            for lang in self._path_map[path]:
                yield lang, self._path_map[path][lang]


class MultiLanguageBlueprint(flask.Blueprint):

    mapper: PathMapper = None

    @injector.construct
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _register_i18n_route(self, fn, route: str, **kwargs):
        all_langs = []
        for lang, path in self.mapper.get_path_translations(route):
            all_langs.append(lang)
            self.route(path, accept_languages=lang, **kwargs)(fn)
        if all_langs:
            self.route(route, ignore_languages=all_langs, **kwargs)(fn)
        else:
            self.route(route, **kwargs)(fn)

    def i18n_route(self, route: str, **kwargs):
        def wrapper(fn):
            self._register_i18n_route(fn, route, **kwargs)
            return fn
        return wrapper


@injector.injectable
class RequestInfo:

    def __init__(self):
        self._remote_ip = None
        self._proxy_ip = None
        self._correl_id = None
        self._client_id = None
        self._request_url = None
        self._user_agent = None
        self._username = None
        self._referrer = None
        self._proc_info_loaded = False
        self._system_username = None
        self._emulated_user = None
        self._logon_time = None
        self._system_remote_addr = None

    def remote_ip(self):
        if self._remote_ip is None and flask.has_request_context():
            if "X-Forwarded-For" in flask.request.headers:
                self._remote_ip = flask.request.headers.getlist("X-Forwarded-For")[0].rpartition(' ')[-1]
            else:
                self._remote_ip = flask.request.remote_addr or 'untrackable'
        return self._remote_ip

    def proxy_ip(self):
        if self._proxy_ip is None and flask.has_request_context():
            if "X-Forwarded-For" in flask.request.headers:
                self._proxy_ip = flask.request.remote_addr or 'untrackable'
        return self._proxy_ip

    def correlation_id(self):
        if self._correl_id is None and flask.has_request_context():
            self._correl_id = flask.request.headers.get("X-Correlation-ID", "")
        return self._correl_id

    def client_id(self):
        if self._client_id is None and flask.has_request_context():
            self._client_id = flask.request.headers.get("X-Client-ID", "")
        return self._client_id

    def request_url(self):
        if self._request_url is None and flask.has_request_context():
            self._request_url = flask.request.url
        return self._request_url

    def user_agent(self):
        if self._user_agent is None and flask.has_request_context():
            self._user_agent = flask.request.user_agent.string
        return self._user_agent

    def username(self):
        if self._username is None and flask.has_request_context():
            self._username = flask_login.current_user.get_id()
        return self._username

    def referrer(self):
        if self._referrer is None and flask.has_request_context():
            self._referrer = flask.request.referrer
        return self._referrer

    def _load_process_info(self):
        if self._proc_info_loaded is False and not flask.has_app_context():
            res = subprocess.run([shutil.which("whoami")], capture_output=True)  # noqa: S603
            txt = res.stdout.decode("utf-8").replace("\t", " ").strip("\r\n\t ")
            while "  " in txt:
                txt = txt.replace("  ", " ")
            pieces = txt.split(" ")
            self._system_username = pieces[0]
            self._emulated_user = pieces[0]
            if len(pieces) > 2:
                self._logon_time = pieces[2] + " " + pieces[3]
            if len(pieces) > 4:
                self._system_remote_addr = pieces[4].strip("()")
            if os.name == "posix":
                res = subprocess.run([shutil.which("who")], capture_output=True)  # noqa: S603
                if res.returncode == 0 and res.stdout:
                    self._emulated_user = res.stdout.decode("utf-8")
            self._proc_info_loaded = True

    def sys_username(self):
        self._load_process_info()
        return self._system_username

    def sys_emulated_username(self):
        self._load_process_info()
        return self._emulated_user

    def sys_logon_time(self):
        self._load_process_info()
        return self._logon_time

    def sys_remote_addr(self):
        self._load_process_info()
        return self._system_remote_addr


def self_url(**kwargs):
    ep = flask.request.endpoint
    args = flask.request.view_args.copy() or {}
    args.update(flask.request.args)
    args.update(kwargs)
    return flask.url_for(ep, **args)


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
            mu += f'<li><a href="{escape(path)}">{escape(gettext(txt))}</a></li>'
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


class SecureBaseForm(BaseForm):

    class Meta(DefaultMeta):
        csrf_class = _FlaskFormCSRF

        @property
        def csrf(self):
            return flask.current_app.config.get("WTF_CSRF_ENABLED", True)

        @property
        def csrf_context(self):
            return flask.session

        @property
        def csrf_secret(self):
            return flask.current_app.config.get("WTF_CSRF_SECRET_KEY", flask.current_app.secret_key)

        @property
        def csrf_time_limit(self):
            return flask.current_app.config.get("WTF_CSRF_TIME_LIMIT", flask.current_app.config["PERMANENT_SESSION_LIFETIME"])

    def __init__(self, controls, *args, **kwargs):
        meta = SecureBaseForm.Meta()
        super().__init__(controls, *args, meta=meta, **kwargs)


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
        if val is True or val is False:
            val = str(val)
        if val is None:
            val = ""
        sel_text = " selected=\"selected\"" if selected else ""
        return f'<option{sel_text} value="{val}">{markupsafe.escape(label)}</option>'


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
        return safe_json(results)

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


class DataColumn:

    def __init__(self, name, header_text, allow_order: bool = False, allow_search: bool = False, show_column: bool = True, formatter: callable = None):
        self.name = name
        self.allow_order = allow_order
        self.allow_search = allow_search
        self.show_column = show_column
        self._header = header_text
        self._formatter = formatter

    def header(self):
        return self._header

    def value(self, data_row):
        raise NotImplementedError()

    def build_filter(self, dq, filter_text):
        return None

    def order_by(self, dq, query, direction):
        return query


class CustomDisplayColumn(DataColumn):

    def __init__(self, name, header_text, display_callback=None):
        super().__init__(name=name, header_text=header_text)
        self._callback = display_callback

    def value(self, data_row):
        return self._callback(data_row)


class ActionListColumn(DataColumn):

    def __init__(self, action_callback=None):
        super().__init__(
            name="_actions",
            header_text=gettext("pipeman.general.actions")
        )
        self._callback = action_callback

    def value(self, data_row):
        return self._callback(data_row).render("table_actions")


class DatabaseColumn(DataColumn):

    def value(self, data_row):
        val = getattr(data_row, self.name)
        if self._formatter and val is not None:
            return self._formatter(val)
        return val

    def build_filter(self, dq, filter_text):
        if self.allow_search:
            return getattr(dq.orm_entity, self.name).like(f"%{filter_text}%")

    def order_by(self, dq, query, direction):
        if self.allow_order:
            col = getattr(dq.orm_entity, self.name)
            if direction == "desc":
                col = col.desc()
            return query.order_by(col)
        return query


class DisplayNameColumn(DatabaseColumn):

    def __init__(self):
        super().__init__("display_names", gettext("pipeman.general.display_name"), allow_search=True)

    def value(self, data_row):
        return MultiLanguageString(json.loads(data_row.display_names))


class DataQuery:

    def __init__(self, orm_entity, wrapper_func=None, extra_filters=None, **filter_by):
        self.orm_entity = orm_entity
        self._filters = filter_by
        self._wrapper_func = wrapper_func
        self._extra_filters = extra_filters

    @injector.inject
    def rows(self, data_table, db: Database = None):
        with db as session:
            query = self._base_query(session)
            query = self._apply_filters(query, data_table)
            query = self._order_query(query, data_table)
            query = self._paginate_query(query, data_table)
            for row in query:
                if self._wrapper_func:
                    yield self._wrapper_func(row)
                else:
                    yield row

    @injector.inject
    def count_all(self, data_table, db: Database = None):
        with db as session:
            query = self._base_query(session)
            return query.count()

    @injector.inject
    def count_filtered(self, data_table, db: Database = None):
        with db as session:
            query = self._base_query(session)
            query = self._apply_filters(query, data_table)
            query = self._paginate_query(query, data_table)
            return query.count()

    def _paginate_query(self, query, data_table):
        return query.offset(data_table.current_index()).limit(data_table.page_size())

    def _order_query(self, query, data_table):
        for cname, direction in data_table.order_columns():
            query = data_table.column(cname).order_by(self, query, direction)
        return query

    def _apply_filters(self, query, data_table):
        text = data_table.search_text()
        if text:
            filters = []
            for col in data_table.columns():
                filt = col.build_filter(self, text)
                if filt is not None:
                    filters.append(filt)
            if filters:
                return query.filter(sa.or_(*filters))
        return query

    def _base_query(self, session):
        query = session.query(self.orm_entity)
        if self._filters:
            query = query.filter_by(**self._filters)
        if self._extra_filters:
            for f in self._extra_filters:
                query = query.filter(f)
        return query


class DataTable:
    """Represents a datatable to be displayed using the datatable jQuery plugin.
    Basically, wraps around a SQLAlchemy query to provide data in a tabular format with paging, searching, etc.
    Columns should be specified as a dictionary where the key is an arbitrary string for the column name with
    entries similar to this one:
    col_name:
        searchable: true to enable searching, must support LIKE expressions
        orderable: true to enable ordering
        default_orderable: specify True for one column only to be the default sort order
        attribute: attribute name on the entity
        action_callback: method name on the wrapper object to get a list of actions
        action_arguments: extra arguments if action_callback is used
        actions: a list of actions to display
        wrap: method on the wrapper object to call to get a value
        convert: function to call with the attribute value
        header: the header text to display
    Action items are a tuple which must contain three elements at least:
    - The path to pass to flask.url_for()
    - The name of the parameter to pass the object ID to (this only works for entity.id values)
    - The translated text to display
    Additional arguments can be specified and will be passed through to flask.url_for().
    Parameters
    ----------
    table_id: str
        The ID of the HTML table.
    entity:
        The entity class to query.
    columns: dict
        A dictionary of columns (see documentation).
    page_size: t.Union[None, int], optional
        The page size (defaults to 50).
    ajax_route: t.Union[None, str], optional
        The route of the AJAX callback for dynamic content loading.
    wrapper_func: t.Union[t.Callable, None], optional
        If specified, the function will be called to wrap each row.
    sql_clause: optional
        If specified, the session query will be filter()'d by this expression first.
    **base_filters
        If specified, the session query will have filter_by() called with these keyword arguments.
    """

    def __init__(
        self,
        table_id: str,
        base_query: DataQuery,
        page_size: t.Union[None, int] = None,
        ajax_route: t.Union[None, str] = None,
        default_order=None
    ):
        """Implement __init__()."""
        self._query = base_query
        self._table_id = table_id
        self._paginate = page_size is not None
        self._page_size = page_size if page_size else None
        self._ajax_route = ajax_route
        self._can_search = False
        self._can_order = False
        self._columns = {}
        self._default_order = default_order

    def add_column(self, col: DataColumn):
        self._columns[col.name] = col
        if col.allow_order:
            self._can_order = True
        if col.allow_search:
            self._can_search = True

    def __str__(self) -> str:
        """Generate the HTML content for the datatable."""
        return self.to_html()

    def __html__(self) -> str:
        return self.to_html()

    def to_javascript(self) -> str:
        """Generate the JavaScript content for the datatable."""
        config = {
            "ajax": {
                "type": "POST"
            },
            "columns": [],
            "searching": False,
            "ordering": False,
            "paging": False,
            "lengthChange": False,
            "autoWidth": False,
            "language": {
                "decimal": gettext("datatable.decimal"),
                "emptyTable": gettext("datatable.emptyTable"),
                "info": gettext("datatable.info"),
                "infoEmpty": gettext("datatable.infoEmpty"),
                "infoFiltered": gettext("datatable.infoFiltered"),
                "infoPostFix": "",
                "thousands": gettext("datatable.thousands"),
                "lengthMenu": gettext("datatable.lengthMenu"),
                "loadingRecords": gettext("datatable.loadingRecords"),
                "processing": "",
                "search": gettext("datatable.search"),
                "zeroRecords": gettext("datatable.zeroRecords"),
                "paginate": {
                    "first": gettext("datatable.paginate.first"),
                    "last": gettext("datatable.paginate.last"),
                    "next": gettext("datatable.paginate.next"),
                    "previous": gettext("datatable.paginate.previous"),
                },
                "aria": {
                    "sortAscending": gettext("datatable.aria.sortAscending"),
                    "sortDescending": gettext("datatable.aria.sortDescending"),
                },
            },
        }
        if self._paginate:
            config["paging"] = True
            config["pageLength"] = self._page_size
        if self._ajax_route:
            config["ajax"]["url"] = self._ajax_route
            config["serverSide"] = True
        if self._can_search:
            config["searching"] = True
        if self._can_order:
            config["ordering"] = True
        for cname in self._columns:
            col = self._columns[cname]
            if not col.show_column:
                continue
            config["columns"].append(
                {
                    "data": cname,
                    "searchable": col.allow_search,
                    "orderable": col.allow_order,
                }
            )
        block = "<script>"
        block += "$(document).ready(function() {\n"
        block += "  $('#{}').DataTable({});".format(self._table_id, json.dumps(safe_json(config)))
        block += "});</script>"
        return Markup(block)

    def columns(self):
        for col in self._columns:
            yield self._columns[col]

    def column(self, cname):
        return self._columns[cname]

    def search_text(self):
        if self._can_search:
            return flask.request.args.get("search[value]", default=None)
        return None

    def current_index(self):
        index = flask.request.args.get("start", type=int, default=0)
        if index is None or index < 0:
            index = 0
        elif index < 0:
            return 0
        return index

    def page_size(self):
        page_size = flask.request.args.get("length", type=int, default=self._page_size)
        if page_size is None or page_size < 10:
            page_size = self._page_size
        elif page_size > 250:
            page_size = 250
        return page_size

    def order_columns(self):
        order = []
        if self._can_order:
            i = 0
            while True:
                col_index = flask.request.args.get(f"order[{i}][column]")
                if col_index is None:
                    break
                col_name = flask.request.args.get(f"columns[{col_index}][data]")
                col_order = "asc"
                if flask.request.args.get(f"order[{i}][dir]") == "desc":
                    col_order = "desc"
                order.append((col_name, col_order))
                i += 1
        return order or self._default_order

    def to_html(self) -> str:
        """Generate the HTML for the data table."""
        html = f'<table id="{self._table_id}" class="data_table" cellpadding="0" cellspacing="0" border="0"><thead><tr>'
        for cname in self._columns:
            if self._columns[cname].show_column:
                html += f'<th>{self._columns[cname].header()}</th>'
        html += "</tr></thead><tbody>"
        for row in self._query.rows(self):
            html += "<tr>"
            for cname in self._columns:
                if self._columns[cname].show_column:
                    html += "<td>{}</td>".format(escape(self._columns[cname].value(row)))
            html += "</tr>"
        html += "</tbody></table>"
        return Markup(html)

    def ajax_response(self) -> dict:
        """Generate the AJAX JSON response for searches and paginating."""
        total_records = self._query.count_all(self)
        total_filtered = self._query.count_filtered(self)
        data = [
            {
                cname: escape(self._columns[cname].value(row))
                for cname in self._columns
            }
            for row in self._query.rows(self)
        ]
        return {
            "data": safe_json(data),
            "recordsFiltered": total_filtered,
            "recordsTotal": total_records,
            "draw": flask.request.args.get("draw", type=int),
        }


def safe_json(json):
    if isinstance(json, dict):
        for key in json:
            json[key] = safe_json(json[key])
        return json
    elif isinstance(json, list):
        new_list = [safe_json(x) for x in json]
        return new_list
    elif json is True or json is False or json is None:
        return json
    elif isinstance(json, str) or isinstance(json, int) or isinstance(json, float):
        return json
    # Fallback to ISO string encoding for easy parsing in Javascript
    elif isinstance(json, datetime.datetime):
        return json.isoformat()
    elif isinstance(json, datetime.date):
        return json.isoformat()
    elif isinstance(json, object):
        if hasattr(json, "__html__"):
            return str(json.__html__())
        if hasattr(json, "__str__"):
            return str(json)
    raise ValueError(f"cannot serialize: {json}")
