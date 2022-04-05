import copy
from email.policy import default
import re
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

workflow_schema = {
    "$id": "http://odahub.io/ontology#workflow-schema",
    "properties": {
        "test": {
            "required": ["call_type", "call_context", "workflow"]
        }
    },
    "required": ["base", "inputs"]
}

# workflow_schema = json.loads(open("workflow-schema.json").read())

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
    T.field_names = ["name", "inputs", "location"]
    T.align = "l"

    for w in r:
        T.add_row([
                w['workflow'].split("#")[1],
                list(w['expects'].keys()),
                w['location']
            ])

    print(T)


@workflow.command()
@click.argument("workflow_name")
@click.option('-R', '--regex', is_flag=True, default=False)
@click.option('-a', '--argument', multiple=True)
def run(workflow_name, argument, regex):
    if regex:
        workflows = [v for k, v in dict_workflows().items() if re.match(workflow_name, k)]
    else:
        workflows = [dict_workflows()[workflow_name]]

    summary = []

    for workflow in workflows:

        logger.debug(json.dumps(workflow, indent=4, sort_keys=True))

        try:
            r = run_workflow({
                "base": workflow,
                "inputs": dict([ a.split("=", 1) for a in argument ])
            })

            logger.info(r)
            if r['status'] == 'success':
                summary.append({'workflow': workflow['workflow'], 'event': 'success'})
            else:
                logger.error('\033[31mPROBLEM\033[0m')
                summary.append({'workflow': workflow['workflow'], 'event': 'failed'})
                continue
            
        except Exception as e:
            logger.error("exception running workflow %s: %s", workflow, e)
            summary.append({'workflow': workflow['workflow'], 'event': 'failed'})        

    for s in summary:
        logger.info(s)


@workflow.command()
@click.argument("workflow_name")
# @click.argument("workflow_name")
# @click.option('-a', '--argument', multiple=True)
@click.option('-c', '--commit')
@click.option('-n', '--no-test', is_flag=True, default=False)
@click.option('-e', '--expire', is_flag=True, default=False)
@click.option('-R', '--regex', is_flag=True, default=False)
@click.option('--fix-function', default=None)
@click.option('--fix-file', default=None)
@click.option('-a', '--test-argument', multiple=True)
def replace(workflow_name, commit, test_argument, no_test, expire, regex, fix_function, fix_file): #, new_name):
    
    if regex:
        workflows = [v for k, v in dict_workflows().items() if re.match(workflow_name, k)]
    else:
        workflows = [dict_workflows()[workflow_name]]

    summary = []

    for workflow in workflows:

        logger.debug(
            "".join(["\nold >>> " + s for s in json.dumps(workflow, indent=4, sort_keys=True).split("\n")])
            )

        r = re.match(r'https://raw.githubusercontent.com/+volodymyrss/+oda_test_kit/+(.*?)/.*', workflow['location'])
        if r is None:
            summary.append({'workflow': workflow['workflow'], 'event': 'no-commit-info'})            
            continue            

        old_commit = r.group(1)
        new_workflow = copy.deepcopy(workflow)
        new_workflow['location'] = new_workflow['location'].replace(old_commit, commit)
        new_workflow['workflow'] = new_workflow['workflow'].replace(old_commit, commit)

        if commit not in new_workflow['workflow']:
            new_workflow['workflow'] += "_" + commit

        ### adapt function
        w_file, w_function = new_workflow['location'].split("::")

        if fix_function is not None:            
            w_function = fix_function

        if fix_file is not None:            
            w_file = fix_file

        new_workflow['location'] = "::".join([w_file, w_function])
        
        logger.debug(
            "".join(["\nnew <<< " + s for s in json.dumps(new_workflow, indent=4, sort_keys=True).split("\n")])
            )

        if new_workflow == workflow:
            logger.error('\033[31mNO CHANGE\033[0m')            

            summary.append({'workflow': workflow['workflow'], 'event': 'no-change'})
            
            continue

        if no_test:
            logger.warning('skipping test')
        else:
            r = run_workflow({
                "base": new_workflow,
                "inputs": dict([ a.split("=", 1) for a in test_argument ])
            },
                timeout=3600)
            logger.info(r)
            if r['status'] != 'success':
                logger.error('\033[31mPROBLEM\033[0m')
                summary.append({'workflow': workflow['workflow'], 'event': 'failed'})
                continue

        r = requests.get(url+"/tests/add",
                        params={
                            'uri': new_workflow['workflow'],
                            'location': new_workflow['location'],
                            'submitter_email': new_workflow['email'],
                            'extra_rdf':''
                        }
                        
        ) #.json()

        logger.debug("%s, %s", r, r.text)

        if expire:
            r = requests.get(url+"/expire",
                        params={
                            'uri': workflow['workflow'],
                        })
            logger.debug("%s, %s", r, r.text)
            summary.append({'workflow': workflow['workflow'], 'event': 'updated-expired'})
        else:
            summary.append({'workflow': workflow['workflow'], 'event': 'updated-not-expired'})

    for s in summary:
        logger.info(s)
            
    
@workflow.command()
@click.argument("workflow_location")
@click.option('-n', '--no-test', is_flag=True, default=False)
@click.option('-a', '--test-argument', multiple=True)
@click.option('-e', '--email', default=None)
@click.option('-i', '--input', multiple=True)
def add(workflow_location, no_test, test_argument, email, input):
    if email is None:
        email = "anonymous"

    new_workflow = {
            'uri': workflow_location.replace("::", "#").replace("https://", "http://"),
            'location': workflow_location,
            'submitter_email': email,
            'extra_rdf':'',
            'call_type': "http://odahub.io/ontology#python_function",
            'call_context': "http://odahub.io/ontology#python3",
        }

    if no_test:
        logger.warning('skipping test')
    else:
        r = run_workflow({
            "base": new_workflow,
            "inputs": dict([ a.split("=", 1) for a in test_argument ])
        },
            timeout=3600)
        logger.info(r)
        if r['status'] != 'success':
            logger.error('\033[31mPROBLEM\033[0m')
            return
        else:
            logger.error('\033[32mSUCCESS\033[0m')

    extra_rdf = ''
    for inp in input:
        extra_rdf += f'<{new_workflow["uri"]}> oda:expects {inp} . \n'

    print(f"extra_rdf: \033[33m{extra_rdf}\033[0m")

    print(json.dumps(new_workflow, indent=4, sort_keys=True))

    r = requests.get(url+"/tests/add",
                    params={
                        'uri': new_workflow['uri'],
                        'location': new_workflow['location'],
                        'submitter_email': new_workflow['submitter_email'],
                        'extra_rdf':extra_rdf,
                    })

    print(r.text)
    print(json.dumps(r.json(), indent=4, sort_keys=True))


if __name__ == "__main__":
    cli()
