import click
from peridio_evk.commands.initialize import initialize
from peridio_evk.commands.devices import virtual_devices_start, virtual_devices_stop, virtual_devices_destroy

@click.group()
def cli():
    pass

cli.add_command(initialize)
cli.add_command(virtual_devices_start)
cli.add_command(virtual_devices_stop)
cli.add_command(virtual_devices_destroy)

if __name__ == "__main__":
    cli()
