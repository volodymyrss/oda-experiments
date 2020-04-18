import click

import logging
import requests

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger("odaworker")

@click.group()
def cli():
    pass

@cli.command()
@click.option("-u", "--url", default="http://in.internal.odahub.io")
def worker(url):
    goal = requests.get(url+"/offer-goal").json()
    logger.info("goal: %s", goal)

if __name__ == "__main__":
    cli()

