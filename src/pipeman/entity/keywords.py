from pipeman.i18n import MultiLanguageString


class Keyword:

    def __init__(self, identifier, machine_key=None, translated_values=None, thesaurus=None, mode=None):
        self._identifier = identifier
        self.machine_key = machine_key
        self.translations = translated_values or {}
        self.thesaurus = thesaurus
        self.mode = mode or "value"

    def __str__(self):
        dns = self.translations.copy()
        if self.machine_key:
            dns["und"] = self.machine_key
        return str(MultiLanguageString(dns))

    def use_machine_key(self):
        return self.machine_key and self.mode == "both"

    def use_value_only(self):
        return self.machine_key and self.mode == "value"

    def to_display(self, primary_locale, use_prefixes: bool = False, prefix_separator: str = ":", force_translations: bool = False):
        # Only use translations
        display_dict = {
            "primary": None,
            "secondary": {},
            'vocab': None
        }
        prefix = self.thesaurus['prefix'] if use_prefixes and self.thesaurus and 'prefix' in self.thesaurus and self.thesaurus['prefix'] else ''
        if prefix:
            prefix = f"{prefix}{prefix_separator}"
        if self.thesaurus:
            title = self.thesaurus_title()
            if title:
                display_dict["vocab"] = f"{prefix}{title}"
        if self.mode == "translate":
            if isinstance(self.translations, str):
                display_dict["primary"] = f"{prefix}{self.translations}"
            else:
                if primary_locale in self.translations:
                    display_dict["primary"] = f"{prefix}{self.translations[primary_locale]}"
                elif "und" in self.translations:
                    display_dict["primary"] = f"{prefix}{self.translations['und']}"
                display_dict["secondary"] = {
                    key: f"{prefix}{self.translations[key]}"
                    for key in self.translations
                    if key != "und" and key != primary_locale and self.translations[key]
                }

        # Only use the machine key
        elif self.mode == "value" and not force_translations:
            display_dict["primary"] = f"{prefix}{self.machine_key}"

        # Use a mix of both (machine key as undefined value)
        else:
            display_dict["primary"] = f"{prefix}{self.machine_key}"
            display_dict["secondary"] = {
                key: f"{prefix}{self.translations[key]}"
                for key in self.translations
                if key != "und" and self.translations[key]
            }
        return display_dict

    def key_identifier(self):
        if self._identifier:
            return self._identifier
        if self.machine_key:
            return self.machine_key

    def thesaurus_title(self):
        if not self.thesaurus:
            return None
        if not ('citation' in self.thesaurus and self.thesaurus['citation']):
            return None
        if not ('title' in self.thesaurus['citation'] and self.thesaurus['citation']['title']):
            return None
        title = self.thesaurus['citation']['title']
        if isinstance(title, str):
            return title
        keys = ['und', 'en']
        keys.extend(title.keys())
        for key in keys:
            if key in title and title[key]:
                return title[key]
        return None

    def thesaurus_group(self):
        if not self.thesaurus:
            return ''
        if 'prefix' in self.thesaurus:
            return self.thesaurus['prefix']
        return self.thesaurus_title() or ''


class KeywordGroup:

    def __init__(self, thesaurus):
        self.thesaurus = thesaurus
        self._keywords = {}

    def append(self, keyword: Keyword):
        self._keywords[keyword.key_identifier()] = keyword

    def keywords(self):
        key_names = list(self._keywords.keys())
        key_names.sort()
        for name in key_names:
            yield self._keywords[name]