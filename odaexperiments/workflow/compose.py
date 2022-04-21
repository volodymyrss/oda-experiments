
# here fetch workflows, options, compose and sort them

# construct workflows from publications by generalizing object

# sort by ML based scores and by other means. explain with graphs

# fetch workflows that output rdf. any workflow outputs rdf. gather it's execution
# fetch and run reasoning workflows here

# use osa verification workflows
# use transient workflows
# use deduced world workflows
# use osa self-test workflows

# contextualize and decontextualize

# cast parameters

# refer to knowledge resolutions

from collections import defaultdict
import logging
import odakb.sparql

from ..aux import timeit, pdict

logger = logging.getLogger(__name__)


@timeit
def get_workflows(f=None):
    sparql_filter = ""
    if f is not None:
        sparql_filter = f

    workflows_dict = defaultdict(dict)

    for t in odakb.sparql.select(
                    f"""?workflow a oda:workflow;
                                  oda:callType ?call_type;
                                  oda:callContext ?call_context;
                                  oda:location ?location;
                                  oda:expects ?expects;
                                  oda:domain ?domain .

                        ?expects a ?expects_type .

                        {sparql_filter}
                              
                        OPTIONAL {{ ?workflow dc:contributor ?email }}

                        NOT EXISTS {{ ?workflow oda:realm oda:expired }}
                    """ ,
                    limit=10000,
                ):  # type: ignore

        logger.info("sparql row: %s", pdict(t))
                
        workflow = workflows_dict[t['workflow']]

        for p, v in t.items():            
            if p == 'expects':
                workflow['expects'] = workflow.get('expects', {})
                workflow['expects'][v.split("#")[-1]] = t['expects_type']                
            elif p in ['location', 'domain']: # find type from ontology
                S = set(workflow.get(p, []))
                S.add(v)
                workflow[p] = list(S)
            else:
                workflow[p] = v
                

    workflows = [{'workflow': k, **v} for k, v in workflows_dict.items()]
        
    logger.info("returning %s workflows", len(workflows))

    return workflows

def workflows_from_papers():
    pass
