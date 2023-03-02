import click
from .vocab_fetch import CIOOSVocabularyManager
from autoinject import injector


@click.group
def cioos():
    pass


@cioos.command
@injector.inject
def update(vm: CIOOSVocabularyManager = None):
    vm.fetch()
