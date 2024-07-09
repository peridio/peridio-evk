import click
from peridio_evk.commands.initialize import initialize
from peridio_evk.commands.devices import (
    devices_start,
    devices_stop,
    device_attach,
)


@click.group()
def cli():
    pass


cli.add_command(initialize)
cli.add_command(devices_start)
cli.add_command(devices_stop)
cli.add_command(device_attach)

if __name__ == "__main__":
    cli()
