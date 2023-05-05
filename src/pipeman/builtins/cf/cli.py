import click
from .util import CFVocabularyManager
from autoinject import injector


@click.group
def cf():
    pass


@cf.command
def update():
    do_update()


@injector.inject
def do_update(vm: CFVocabularyManager = None):
    vm.fetch()
