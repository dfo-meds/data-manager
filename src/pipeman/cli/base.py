"""Base classes for the CLI for pipeman"""
import click


class CommandLineInterface(click.MultiCommand):
    """Implements multicommand by storing a dictionary of commands to call."""

    def __init__(self, app, commands: dict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands = commands
        self.app = app

    def list_commands(self, ctx):
        return self.commands.keys()

    def get_command(self, ctx, name):
        if name in self.commands:
            return self.commands[name]
        return None

    def __call__(self, *args, **kwargs):
        with self.app.app_context():
            with self.app.test_request_context():
                super().__call__(*args, **kwargs)
