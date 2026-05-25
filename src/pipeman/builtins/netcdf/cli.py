import click
from .util import CFVocabularyManager
from autoinject import injector


@click.group
def netcdf():
    pass


@netcdf.command
def update():
    do_update()


@injector.inject
def do_update(vm: CFVocabularyManager = None):
    vm.fetch()
