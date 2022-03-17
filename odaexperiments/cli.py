import logging
import click
from .workflow import workflow
from .worker import worker

logger = logging.getLogger("odaexperiments")


@click.group()
@click.option("-d", "--debug", is_flag=True, default=False)
def cli(debug):
    if debug:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logging.basicConfig(level=log_level)
    
    logging.getLogger().setLevel(log_level)
    
cli.add_command(workflow)
cli.add_command(worker)

if __name__ == "__main__":
    cli()

