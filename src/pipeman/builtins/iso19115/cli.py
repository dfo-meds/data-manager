import click
from .vocab_fetch import ISO19115VocabularyManager
from autoinject import injector


@click.group
def iso19115():
    pass


@iso19115.command
def update():
    do_update()


@injector.inject
def do_update(vm: ISO19115VocabularyManager = None):
    vm.fetch()
