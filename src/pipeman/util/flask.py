import wtforms as wtf
from wtforms.form import BaseForm
from pipeman.i18n import TranslationManager
from autoinject import injector


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
    def __init__(self, template_field, field_kwargs=None, *args, **kwargs):
        self.template_field = template_field
        self.template_args = field_kwargs or {}
        if "label" in self.template_args:
            del self.template_args["label"]
        super().__init__(self._build_field_list(), *args, **kwargs)

    def _build_field_list(self):
        return {
            lang: self.template_field(label=lang.upper(), **self.template_args)
            for lang in self.tm.supported_languages()
        }
