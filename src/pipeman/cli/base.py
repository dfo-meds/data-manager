"""Base classes for the CLI for pipeman"""
import click


class CommandLineInterface(click.MultiCommand):
    """Implements multicommand by storing a dictionary of commands to call."""

    def __init__(self, commands: dict, *args, **kwargs):
        self.commands = commands
        super().__init__(*args, **kwargs)

    def list_commands(self, ctx):
        return self.commands.keys()

    def get_command(self, ctx, name):
        return self.commands[name]
