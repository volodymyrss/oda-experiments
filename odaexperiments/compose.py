
# here fetch workflows, options, compose and sort them

# construct workflows from publications by generalizing object

# sort by ML based scores and by other means. explain with graphs

# fetch workflows that output rdf. any workflow outputs rdf. gather it's execution


# use osa verification workflows
# use transient workflows
# use deduced world workflows
# use osa self-test workflows


# refer to knowledge resolutions

from collections import defaultdict
import json
import logging
import pprint
import time
import odakb.sparql
from odakb.sparql import nuri

logger = logging.getLogger(__name__)

def pdict(d):
    return json.dumps(d, indent=4, sort_keys=True)

def timeit(f):
    def print_time(t0):
        logger.getChild("timeit").debug("spent %s in %s", time.time() - t0, f.__name__)

    def _f(*args, **kwargs):
        t0 = time.time()
        try:
            R = f(*args, **kwargs)            
            print_time(t0)
            return R
        except Exception as e:
            print_time(t0)
            raise

    return _f

@timeit
def get_workflows(f=None):
    tests=[]

    sparql_filter = ""
    if f is not None:
        sparql_filter = f

    workflows_dict = {}

    for t in odakb.sparql.select(
                    f"""?workflow a oda:workflow;
                                  oda:callType ?call_type;
                                  oda:callContext ?call_context;
                                  oda:location ?location;
                                  oda:expects ?expects;
                                  oda:domain ?domain .

                        ?expects a ?ex_type .

                        {sparql_filter}
                              
                        OPTIONAL {{ ?workflow dc:contributor ?email }}

                        NOT EXISTS {{ ?workflow oda:realm oda:expired }}
                    """ ,
                    limit=10000,
                ):  # type: ignore

        logger.info("sparql row: %s", pdict(t))

        workflow = {}
        workflows_dict[t['workflow']] = workflow

        for p, v in t.items():            
            if p not in workflow:
                workflow[p] = v
            else:
                if not isinstance(workflow[p], list):
                    workflow[p] = [workflow[p]]
                workflow[p].append(v)

    workflows = [{'workflow': k, **v} for k, v in workflows_dict.items()]
        
    logger.info("returning %s workflows", len(workflows))

    return tests

def workflows_from_papers():
    pass
