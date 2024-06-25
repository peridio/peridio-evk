import click
from peridio_evk.commands.configure import configure
from peridio_evk.commands.product import create_product

@click.group()
def cli():
    pass

cli.add_command(configure)
cli.add_command(create_product)

if __name__ == "__main__":
    cli()
