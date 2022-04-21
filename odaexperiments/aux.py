from asyncio.log import logger
import json
import logging
import time

from difflib import SequenceMatcher


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


class KeyErrorSuggestions(KeyError):
    def __init__(self, key, avail_keys) -> None:
        self.key = key
        self.avail_keys = avail_keys

    def __str__(self) -> str:
        return f"KeyError: {self.key}\n" + \
               f"available: \n{pdict(list(sorted(self.avail_keys, key=lambda x:-SequenceMatcher(None, self.key, x).ratio())))}"

def get_dict(D, k):
    try:
        return D[k]
    except KeyError:
        raise KeyErrorSuggestions(k, D.keys())
        