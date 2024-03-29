
# here fetch workflows, options, compose and sort them

# sort by ML based scores and by other means. explain with graphs

# fetch workflows that output rdf. any workflow outputs rdf. gather it's execution

# another equivalent example of function ontology is this one https://fno.io/ontology/


import builtins
import copy
from email.policy import default
import os
import re
import shutil
import time
from traceback import format_exc, print_stack, format_stack
import click

import logging
import hashlib

import prettytable

from odaexperiments.workflow.compose import get_workflows

from .run import run as run_workflow
from .aux import get_dict

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

def list_workflows():
    logger.info("requesting workflows")
    t0 = time.time()
    r = requests.get(url+"/workflows?json").json()
    logger.info("query took %.2lg seconds", time.time() - t0)
    logger.debug(json.dumps(r, indent=4, sort_keys=True))
    return r


def list_workflows_noservice():
    logger.info("requesting workflows")
    r = get_workflows()
    logger.debug(json.dumps(r, indent=4, sort_keys=True))
    return r


def dict_workflows(short_name, lister=list_workflows):
    if short_name:
        return {w['workflow'].split("#")[1]:w for w in lister()}
    else:
        return {w['workflow']:w for w in lister()}        
    

@cli.command("list")
@click.option("-a", "--all", is_flag=True)
@click.option("-l", "--long", is_flag=True)
def _list(all, long):
    rdf_init()        

    if all:
        r = list_workflows_noservice()
    else:
        r = list_workflows()
    
    T = PrettyTable()    
    T.field_names = ["#", "name", "domains", "inputs", "location"]
    T.max_width = shutil.get_terminal_size().columns
    T.align = "l"
    T.hrules = prettytable.ALL

    for i, w in enumerate(r):
        T.add_row([
                i,
                w['workflow'] if long else w['workflow'].split("#")[1],
                "\n".join([d.split("#")[-1] for d in w.get('domain', [])]),
                "\n".join([f"{k} ({v})" for k, v in w.get('expects', {}).items()]),
                "\n".join(w['location']) if isinstance(w['location'], list) else w['location']
            ])

    print(T)


@cli.command()
@click.argument("workflow_name")
@click.option('-s', '--short-name', is_flag=True, default=False)
@click.option('-R', '--regex', is_flag=True, default=False)
@click.option('-i', '--input', multiple=True)
@click.option('-a', '--all', is_flag=True)
def run(workflow_name, input, regex, short_name, all):
    if all:
        lister = list_workflows_noservice
    else:
        lister = list_workflows
    

    if regex:
        workflows = [v for k, v in dict_workflows(short_name, lister=lister).items() if re.match(workflow_name, k)]
    else:        
        workflows = [get_dict(dict_workflows(short_name, lister=lister), workflow_name)]

    summary = []

    for workflow in workflows:

        logger.debug(json.dumps(workflow, indent=4, sort_keys=True))

        try:
            inputs = {}

            for i in input:
                i_k, i_v = i.split("=", 1)
                if ":" in i_v:
                    i_v, i_t = i_v.split(":")
                else:
                    i_t = 'str'

                i_t = getattr(builtins, i_t) 

                inputs[i_k] = i_t(i_v)

            r = run_workflow({
                "base": workflow,
                "inputs": inputs
            })

            logger.info(r)
            if r['status'] == 'success':
                summary.append({'workflow': workflow['workflow'], 'event': 'success'})
            else:
                logger.error('\033[31mPROBLEM\033[0m')
                summary.append({'workflow': workflow['workflow'], 'event': 'failed'})
                continue
            
        except Exception as e:
            logger.error("exception running workflow %s: %s; %s", workflow, e, format_exc())
            summary.append({'workflow': workflow['workflow'], 'event': 'failed'})        

    for s in summary:
        logger.info(s)


@cli.command()
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
        workflows = [v for k, v in dict_workflows(short_name=False).items() if re.match(workflow_name, k)]
    else:
        workflows = [dict_workflows(short_name=False)[workflow_name]]

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
            
    
@cli.command()
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
