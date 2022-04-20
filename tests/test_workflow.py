import logging

logger = logging.getLogger()

def test_get_workflows():
    from odaexperiments.compose import get_workflows

    for w in get_workflows():
        logger.info("%s %s %s", w['workflow'], w['location'], w['expects'])