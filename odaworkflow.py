import click

import logging
import hashlib

import pprint

import json

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger("odaworker")

@click.group()
def cli():
    pass

import jsonschema

workflow_schema = json.loads(open("workflow-schema.json").read())

def validate_workflow(w):
    jsonschema.validate(w, workflow_schema)


def w2uri(w, prefix="data"):
    validate_workflow(w)
    return "data:"+prefix+"-"+hashlib.sha256(json.dumps(w, sort_keys=True).encode()).hexdigest()[:16]
