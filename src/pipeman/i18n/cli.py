import click
from autoinject import injector
from pipeman.util import System
from .util import TranslatableStringFinder
import yaml
import pathlib


@click.group
def i18n():
    pass


@i18n.command
@click.argument("file_path")
@injector.inject
def update(file_path, s: System = None):
    file_path = pathlib.Path(file_path)
    existing = {}
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as h:
            existing = yaml.safe_load(h) or {}
    finder = TranslatableStringFinder()
    results = finder.search_directory(s.i18n_dirs)

    for key in results:
        if key not in existing:
            existing[key] = ""
    with open(file_path, "w", encoding="utf-8") as h:
        h.write(yaml.dump(existing, allow_unicode=True))
