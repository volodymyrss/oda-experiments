import click

import logging
import requests

import time

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger("odaworker")

@click.group()
def cli():
    pass

@cli.command()
@click.option("-u", "--url", default="http://in.internal.odahub.io")
def worker(url):

    t0 = time.time()
    r = requests.get(url+"/offer-goal")
    logger.info("query took %.2lg seconds", time.time() - t0)

    if r.status_code != 200:
        logger.error("problem fetching goal: %s", r)
        print(r.text)
        return

    goal = r.json()
    logger.info("goal: %s", goal)

if __name__ == "__main__":
    cli()

