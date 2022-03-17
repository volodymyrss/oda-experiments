import time
import click

import logging
import hashlib

from .run import run as run_workflow

import json

import jsonschema # type: ignore
from prettytable import PrettyTable

from odakb.sparql import nuri # type: ignore
from odakb.sparql import init as rdf_init
import requests

url = "https://oda-experiments.obsuks1.unige.ch/"

logger=logging.getLogger("odaworker.workflow")

@click.group()
def cli():
    pass


workflow_schema = json.loads(open("workflow-schema.json").read())

def validate_workflow(w):
    jsonschema.validate(w, workflow_schema)


def w2uri(w, prefix="data"):
    validate_workflow(w)
    return "data:"+prefix+"-"+hashlib.sha256(json.dumps(w, sort_keys=True).encode()).hexdigest()[:16]


@click.group()
def workflow():
    pass


def list_workflows():
    logger.info("requesting workflows")
    t0 = time.time()
    r = requests.get(url+"/workflows?json").json()
    logger.info("query took %.2lg seconds", time.time() - t0)
    logger.debug(json.dumps(r, indent=4, sort_keys=True))
    return r


def dict_workflows():
    return {w['workflow'].split("#")[1]:w for w in list_workflows()}
    

@workflow.command("list")
def _list():
    rdf_init()        

    r = list_workflows()
    
    T = PrettyTable()
    T.field_names = ["name", "inputs"]
    T.align = "l"

    for w in r:
        T.add_row([
                w['workflow'].split("#")[1],
                list(w['expects'].keys()),
            ])

    print(T)


@workflow.command()
@click.argument("workflow_name")
def run(workflow_name):

    workflow = dict_workflows()[workflow_name]

    logger.debug(workflow)

    run_workflow({
       "base": workflow,
       "inputs": {}
    })


if __name__ == "__main__":
    cli()
