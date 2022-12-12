import wtforms as wtf
from wtforms.form import BaseForm
from pipeman.i18n import TranslationManager, DelayedTranslationString
from autoinject import injector
from flask_wtf import FlaskForm
import flask
import math


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
            fields['und'] = self.template_field(label='UND', **self.template_args)
        fields.update({
            lang: self.template_field(label=lang.upper(), **self.template_args)
            for lang in self.tm.supported_languages()
        })
        return fields
