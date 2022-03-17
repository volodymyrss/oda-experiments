import click

import logging
import requests

import pprint

import socket

import time
import json

import odaexperiments.run as odarun
from odaexperiments.workflow import validate_workflow, w2uri
from odakb.sparql import nuri # type: ignore
from odakb.sparql import init as rdf_init

logger=logging.getLogger("odaworker")

@click.group()
def cli():
    pass


@cli.command()
@click.option("-u", "--url", default="https://oda-experiments.obsuks1.unige.ch/")
@click.option("-1", "--one-shot", is_flag=True, default=False)
@click.option("-n", "--dry-run", is_flag=True, default=False)
@click.option("-t", "--timeout", default=600)
@click.option("-p", "--period", default=35)
def worker(url, dry_run, one_shot, timeout, period):
    rdf_init()

    nskip=0

    while True:
        t0 = time.time()
        
        logger.info("requesting goal")
        r = requests.get(url+"/offer-goal", params=dict(n=nskip, f='?w oda:callType oda:python_function'))
        logger.info("query took %.2lg seconds", time.time() - t0)

        if r.status_code != 200:
            logger.error("problem fetching goal: %s", r)
            print(r.text)
            time.sleep(period)
            continue

        goal = r.json().get('goal', None)

        if goal is None:
            logger.warning("no more goals! sleeping")
            time.sleep(period)
            nskip=0
            continue

        goal_uri = r.json()['goal_uri']

        logger.info("goal: %s", pprint.pformat(goal))
        logger.info("got goal uri: %s", goal_uri)
        validate_workflow(goal)

        if nuri(w2uri(goal, "goal")) != nuri(goal_uri):
            raise Exception("goal uri mismatch:", nuri(w2uri(goal, "goal")), nuri(goal_uri))

        try:
            logger.info("running!")
            data = odarun.run(goal, timeout=timeout)
            nskip=0
        except odarun.UnsupportedCallType as e:
            nskip+=1
            logger.error("has been offerred unsupported call type (%s) in %s! "
                         "we must have made wrong request; skipping to %i", 
                         e, goal, nskip)
            time.sleep(period)
            continue

        worker = dict(hostname=socket.gethostname(), time=time.time())
        
        if not dry_run:
            while True:
                try:
                    r = requests.post(url+"/report-goal", json=dict(goal=goal, data=data, worker=worker, goal_uri=goal_uri))

                    print(r.text)

                    print(pprint.pformat(r.json()))
                    break
                except Exception as e:
                    print("failed to report:", e,"retrying")
                    time.sleep(period)

        else:
            print("dry run, not reporting")

        if one_shot:
            break

        logger.info("sleeping too the next goal")
        #time.sleep(period)

if __name__ == "__main__":
    cli()

