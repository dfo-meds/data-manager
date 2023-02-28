import re
import os
import pathlib


class TranslatableStringFinder:

    def __init__(self):
        self._py_res = [
            re.compile(r'gettext\([\'"]([A-Za-z_\.-]*?)[\'"]\)'),
            re.compile(r'UserInputError\([\'"]([A-Za-z_\.-]*?)[\'"]\)'),
            re.compile(r'DelayedTranslationString\([\'"]([A-Za-z_\.-]*?)[\'"]\)'),
            re.compile(r'FormValueError\([\'"]([A-Za-z_\.-]*?)[\'"]\)'),
            re.compile(r'\.add_action\([\'"]([A-Za-z_\.]*?)[\'"]')
        ]
        self._jinja_res = [
            re.compile(r'\{\{[ ]{0,}\'([A-Za-z_\.-]*?)\'[ ]{0,}\|[ ]{0,}gettext[ ]{0,}\}\}'),
            re.compile(r'\{\{[ ]{0,}"([A-Za-z_\.-]*?)"[ ]{0,}\|[ ]{0,}gettext[ ]{0,}\}\}')
        ]

    def search_directory(self, directory: str, recursive: bool = True):
        results = set()
        search = [directory] if isinstance(directory, str) else list(directory)
        while search:
            directory = pathlib.Path(search.pop())
            if not directory.exists():
                continue
            for file in os.scandir(directory):
                if file.name.endswith(".py"):
                    results.update(self.search_in_python_file(file.path))
                elif file.name.endswith(".html") or file.name.endswith(".xml"):
                    results.update(self.search_in_jinja_template(file.path))
                elif recursive and file.is_dir() and file.name not in [".", ".."]:
                    search.append(file.path)
        return results

    def search_in_jinja_template(self, template_file: str):
        results = set()
        with open(template_file, "r") as h:
            contents = h.read()
            for regex in self._jinja_res:
                for result in regex.findall(contents):
                    results.add(result)
        return results


    def search_in_python_file(self, py_file: str):
        results = set()
        with open(py_file, "r") as h:
            contents = h.read()
            for regex in self._py_res:
                for result in regex.findall(contents):
                    results.add(result)
        return results

