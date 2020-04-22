import click

import logging
import requests

import pprint

import socket

import time
import json

import odarun
from odaworkflow import validate_workflow, w2uri
from odakb.sparql import nuri
from odakb.sparql import init as rdf_init

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger("odaworker")

@click.group()
def cli():
    pass


@cli.command()
@click.option("-u", "--url", default="http://in.internal.odahub.io/odatests")
@click.option("-1", "--one-shot", is_flag=True, default=False)
@click.option("-n", "--dry-run", is_flag=True, default=False)
def worker(url, dry_run, one_shot):
    rdf_init()

    while True:
        t0 = time.time()
        r = requests.get(url+"/offer-goal")
        logger.info("query took %.2lg seconds", time.time() - t0)

        if r.status_code != 200:
            logger.error("problem fetching goal: %s", r)
            print(r.text)
            return

        goal = r.json().get('goal', None)
        if goal is None:
            logger.warning("no more goals! sleeping")
            time.sleep(15)
            continue

        goal_uri = r.json()['goal_uri']

        logger.info("goal: %s", pprint.pformat(goal))
        logger.info("got goal uri: %s", goal_uri)

        validate_workflow(goal)

        if nuri(w2uri(goal, "goal")) != nuri(goal_uri):
            raise Exception("goal uri mismatch:", nuri(w2uri(goal, "goal")), nuri(goal_uri))


        data = odarun.run(goal)

        worker = dict(hostname=socket.gethostname(), time=time.time())
        
        if not dry_run:
            r = requests.post(url+"/report-goal", json=dict(goal=goal, data=data, worker=worker, goal_uri=goal_uri))

            print(r.text)

            print(pprint.pformat(r.json()))
        else:
            print("dry run, not reporting")

        if one_shot:
            break

        time.sleep(5)

if __name__ == "__main__":
    cli()

