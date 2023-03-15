import click
from .vocab_fetch import CIOOSVocabularyManager
from autoinject import injector


@click.group
def cioos():
    pass


@cioos.command
def update():
    do_update()


@injector.inject
def do_update(vm: CIOOSVocabularyManager = None):
    vm.fetch()
