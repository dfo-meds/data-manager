"""Language detection implementation

The basic implementation relies on the following

- The value of the "lang" query string argument.
- The languages in the Accept-Language header, in order given there
- A default fallback set when constructing this class
"""
import flask
import typing as t


class BasicRequestLanguageDetector:
    """Responsible for detecting languages."""

    def __init__(self, default_language='en'):
        self._default_lang = default_language

    def detect_language(self, supported_languages: t.List[str]) -> str:
        """Returns a selection from supported_languages that the user wants to see."""
        if not supported_languages:
            raise ValueError("At least one supported language required")
        if flask.has_request_context():
            if "languages" not in flask.g:
                opts = []
                # The query string option is highest priority, if available
                qs = flask.request.args.get("lang")
                if qs:
                    opts.append((qs, 2))
                # Add all the entries from Accept-Language
                for x in flask.request.headers.get("Accept-Language", "").split(","):
                    p = x.split(";")
                    q = 1
                    if len(p) > 1:
                        q = float(p[1][2:])
                    opts.append((p[0], q))
                    if len(p[0]) > 2:
                        opts.append((p[0][0:2], q - 1))
                # sort them so the highest priority is first
                opts.sort(key=lambda x: x[1], reverse=True)
                flask.g.languages = opts
            # Check them in order and use the first one that is supported
            for key, _ in flask.g.languages:
                if key in supported_languages:
                    return key
        if self._default_lang in supported_languages:
            return self._default_lang
        return supported_languages[0]
