from copy import deepcopy

from autoinject import injector
import markupsafe


@injector.injectable_global
class LanguageDetector:

    def detect_language(self, supported_languages) -> str:
        return 'en'


@injector.injectable_global
class TranslationManager:

    def get_text(self, text_key: str, default: str = None) -> str:
        return default if default is not None else text_key

    def supported_languages(self):
        return ['en', 'fr']


class BaseTranslatableString:

    def __init__(self, *format_args, **format_kwargs):
        self.format_args = format_args or []
        self.format_kwargs = format_kwargs or {}

    def __mod__(self, args):
        if hasattr(args, "keys"):
            return self.format(**args)
        elif hasattr(args, '__iter__') and not isinstance(args, str):
            return self.format(*args)
        else:
            return self.format(args)

    def __copy__(self):
        return self.copy()

    def __html__(self):
        return self.render()

    def __str__(self):
        return self.render()

    def __call__(self, **kwargs):
        return self.render(**kwargs)

    def render(self, **kwargs):
        if self.format_args or self.format_kwargs:
            return self._render_str(**kwargs).format(*self.format_args, **self.format_kwargs)
        return self._render_str(**kwargs)

    def copy(self):
        raise NotImplementedError

    def _render_str(self, **kwargs):
        raise NotImplementedError

    def format(self, *args, **kwargs):
        obj = self.copy()
        obj.format_args.extend(args)
        obj.format_kwargs.update(kwargs)
        return obj


class DelayedTranslationString(BaseTranslatableString):

    def __init__(self, text_key, default=None, *args, **kwargs):
        super().__init__(args, kwargs)
        self.text_key = text_key
        self.default = default

    def copy(self):
        return DelayedTranslationString(self.text_key, self.default)

    @injector.inject
    def _render_str(self, tm: TranslationManager = None, **kwargs):
        return tm.get_text(self.text_key, self.default)


class MultiLanguageString(BaseTranslatableString):

    def __init__(self, language_map: dict, *args, **kwargs):
        super().__init__(args, kwargs)
        self.language_map = language_map

    def __bool__(self):
        return any(self.language_map[x] for x in self.language_map)

    @injector.inject
    def _render_str(self, language=None, tm: TranslationManager = None, ld: LanguageDetector = None, **kwargs):
        lang_opts = list(self.language_map.keys())
        lang = language if language is not None and language in lang_opts else ld.detect_language(lang_opts)
        use_blank = lang in self.language_map
        if lang in self.language_map and self.language_map[lang]:
            return self.language_map[lang]
        if "und" in self.language_map and self.language_map["und"]:
            return self.language_map["und"]
        if use_blank:
            return ""
        return tm.get_text("pipeman.general.unknown")

    def keys(self):
        return self.language_map.keys()

    def __len__(self):
        return len(self.language_map)

    def __getitem__(self, key):
        if isinstance(key, str) and key in self.language_map:
            return self.render(language=key)
        raise KeyError(key)

    def __contains__(self, key):
        return key in self.language_map

    def deep_copy(self, memodict):
        return MultiLanguageString(deepcopy(self.language_map))

    def copy(self):
        return MultiLanguageString(self.language_map)


class MultiLanguageLink(MultiLanguageString):

    def __init__(self, link, *args, **kwargs):
        self.link = link
        super().__init__(*args, **kwargs)

    def render(self, **kwargs):
        text = super().render(**kwargs)
        return markupsafe.Markup(f'<a href="{markupsafe.escape(self.link)}">{markupsafe.escape(text)}</a>')
