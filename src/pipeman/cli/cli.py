import click

class CommandLineInterface(click.MultiCommand):

    def __init__(self, commands: dict, *args, **kwargs):
        self.commands = commands
        super().__init__(*args, **kwargs)

    def list_commands(self, ctx):
        return self.commands.keys()

    def get_command(self, ctx, name):
        return self.commands[name]
