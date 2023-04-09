import re
import os
import pathlib
import yaml


class TranslatableStringFinder:

    def __init__(self):
        self._py_res = [
            re.compile(r'gettext\([ \t\r\n]{0,}[\'"]([A-Za-z_\.-]*?)[\'"]'),
            re.compile(r'UserInputError\([ \t\r\n]{0,}[\'"]([A-Za-z_\.-]*?)[\'"]'),
            re.compile(r'DelayedTranslationString\([ \t\r\n]{0,}[\'"]([A-Za-z_\.-]*?)[\'"]'),
            re.compile(r'FormValueError\([ \t\r\n]{0,}[\'"]([A-Za-z_\.-]*?)[\'"]'),
            re.compile(r'ValidationResult\([ \t\r\n]{0,}[\'"]([A-Za-z_\.-]*?)[\'"]'),
            re.compile(r'flasht\([ \t\r\n]{0,}[\'"]([A-Za-z_\.-]*?)[\'"]'),
            re.compile(r'\.add_action\([ \t\r\n]{0,}[\'"]([A-Za-z_\.]*?)[\'"]')
        ]
        self._jinja_res = [
            re.compile(r'\{\{[ ]{0,}\'([A-Za-z_\.-]*?)\'[ ]{0,}\|[ ]{0,}gettext[ ]{0,}\}\}'),
            re.compile(r'\{\{[ ]{0,}"([A-Za-z_\.-]*?)"[ ]{0,}\|[ ]{0,}gettext[ ]{0,}\}\}')
        ]

    def search_directory(self, directory: str, recursive: bool = True, with_origin: bool = False):
        results = set()
        search = [directory] if isinstance(directory, str) else list(directory)
        while search:
            directory = pathlib.Path(search.pop())
            if not directory.exists():
                continue
            for file in os.scandir(directory):
                if file.name.endswith(".py"):
                    results.update(self.search_in_python_file(file.path, with_origin))
                elif file.name.endswith(".html") or file.name.endswith(".xml"):
                    results.update(self.search_in_jinja_template(file.path, with_origin))
                elif recursive and file.is_dir() and file.name not in [".", ".."]:
                    search.append(file.path)
        return results

    def search_locale_files(self, directory: str):
        results = set()
        for file in os.scandir(directory):
            if file.name.endswith(".yaml") or file.name.endswith(".yml"):
                results.update(self.search_in_yaml_file(file.path))
        return results

    def search_in_yaml_file(self, yaml_file: str):
        results = set()
        with open(yaml_file, "r", encoding="utf-8") as h:
            contents = yaml.safe_load(h)
            if isinstance(contents, dict):
                results.update(contents.keys())
        return results

    def search_in_jinja_template(self, template_file: str, with_origin: bool = False):
        results = set()
        with open(template_file, "r", encoding="utf-8") as h:
            contents = h.read()
            for regex in self._jinja_res:
                for result in regex.findall(contents):
                    results.add(result if not with_origin else (result, template_file))
        return results


    def search_in_python_file(self, py_file: str, with_origin: bool = False):
        results = set()
        with open(py_file, "r", encoding="utf-8") as h:
            contents = h.read()
            for regex in self._py_res:
                for result in regex.findall(contents):
                    results.add(result if not with_origin else (result, py_file))
        return results

