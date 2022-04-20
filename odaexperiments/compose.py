
# here fetch workflows, options, compose and sort them

# sort by ML based scores and by other means. explain with graphs

# fetch workflows that output rdf. any workflow outputs rdf. gather it's execution

# construct workflows from publications by generalizing object


# use osa verification workflows
# use transient workflows
# use deduced world workflows
# use osa self-test workflows


# refer to knowledge resolutions

import logging
import pprint
import odakb.sparql
from odakb.sparql import nuri

logger = logging.getLogger(__name__)

def get_workflows(f=None):
    tests=[]

    sparql_filter = ""
    if f is not None:
        sparql_filter = f


    for t in odakb.sparql.select(
                    f"""?workflow a oda:workflow;
                                  oda:callType ?call_type;
                                  oda:callContext ?call_context;
                                  oda:location ?location .

                        {sparql_filter}
                              
                        OPTIONAL {{ ?workflow dc:contributor ?email }}

                        NOT EXISTS {{ ?workflow oda:realm oda:expired }}
                    """ ,
                    limit=10000,
                ):  # type: ignore

        logger.info("selected workflow entry: %s", t)


        t['domains'] = odakb.sparql.select(query="""
                        {workflow} oda:domain ?domain
                        """.format(workflow=nuri(t['workflow'])))
        
        t['expects'] = {}

        for r in odakb.sparql.select(query="""
                        <{workflow}> oda:expects ?expectation .
                        ?expectation a ?ex_type .
                        """.format(workflow=t['workflow'])):  # type: ignore
            #if 

            binding = r['expectation'].split("#")[1][len("input_"):]

            t['expects'][binding] = r['ex_type']

        logger.info("created test (have %s already): \n" + pprint.pformat(t), len(tests))

        tests.append(t)

    logger.info("returning %s workflows", len(tests))

    return tests