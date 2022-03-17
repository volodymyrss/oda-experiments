import requests
import time
import json
from subprocess import PIPE, Popen, STDOUT
from threading  import Thread
from queue import Queue, Empty

import os
import re

class UnsupportedCallType(Exception):
    pass

def run(w, timeout=600):
    print("run this", w)

    if w['base']['call_type'] == "http://odahub.io/ontology#python_function" \
        and w['base']['call_context'] == "http://odahub.io/ontology#python3":
            return run_python_function(w, timeout=timeout)
    
    return dict(result={}, status='unsupported')
    # raise UnsupportedCallType("unable to run this calltype:", w['base']['call_type'])

def run_python_function(w, timeout=600):
    try:
        url, func = w['base']['location'].split("::")
    except Exception as e:
        # raise UnsupportedCallType("can not split", w['base']['location'], e)
        return dict(result=f"can not split {w['base']['location']} {e}", status="unsupported")

    pars = ",".join(["%s=\"%s\""%(k,v) for k,v in w['inputs'].items()])

    time_constrain = None

    for k,v in w['inputs'].items():
        if 'timestamp' in k:
            time_constrain = float(v)

    if time_constrain is not None:
        if time_constrain < time.time() - 3600*3:
            print(f"time-constrained goal obsolete: {time_constrain - time.time()} < {- 3600*3}!")

            result = dict(stdout='')
            status = 'obsolete'

            return dict(result=result, status=status)
    
    #if re.match("https://raw.githubusercontent.com/volodymyrss/oda_test_kit/+[0-9a-z]+?/test_[a-z0-9]+?.py", url):
    if re.match("https://raw.githubusercontent.com/volodymyrss/oda_test_kit/+[0-9a-z]+?/[a-z0-9_]+?.py", url):
        print("found valid url", url)
    else:
        raise UnsupportedCallType("invalid url: %s!"%url)
    
    #if re.match("test_[a-z0-9]+?", func):
    if re.match("[a-z0-9_]+?", func):
        print("found valid func:", func)
    else:
        raise Exception("invalid func: %s!"%func)


    urls = [
            url.replace("https://raw.githubusercontent.com/volodymyrss/oda_test_kit/", 
                        "https://raw.githubusercontent.com/oda-hub/oda_test_kit/"
                        ),        
            url.replace("https://raw.githubusercontent.com/volodymyrss/oda_test_kit/", 
                        "https://gitlab.astro.unige.ch/savchenk/osa_test_kit/raw/"
                        ),
            url,
            ]

    
    r = None
    for url in urls:
        print("fetching url option %s ..."%url)
        r = requests.get(url)

        if r.status_code == 200:
            break
        else:
            print("unable to reach url %s: %s"%(url, r))

    if r is None:
        raise Exception("all urls failed!")

    c = r.text
    c += "\n\nresult=%s(%s)"%(func, pars)
    c += "\n\nimport json"
    c += "\n\nprint('RESULT:', json.dumps(result))"

    print("calling python with:\n", "\n>".join(c.split("\n")))


    stdout = ""

    p = Popen(["python"], 
                          stdin=PIPE, 
                          stdout=PIPE, 
                          stderr=STDOUT, 
                          env={**os.environ, "PYTHONUNBUFFERED":"1"},
                          bufsize=0)

    p.stdin.write(c.encode())

    p.stdin.close()

    def enqueue_output(out, queue):
        for line in iter(out.readline, b''):
            queue.put(line)
        out.close()

    q = Queue()
    t = Thread(target=enqueue_output, args=(p.stdout, q))
    t.daemon = True 
    t.start()

    time_spent = 0
    while True:
        try:
            l = q.get_nowait() # or q.get(timeout=.1)
        except Empty:
            print('no output', time_spent, 's since start')
            if p.poll() is not None:
                print('\033[32mterminated!\033[0m')
                break
            time.sleep(1)
            time_spent += 1
            if time_spent > timeout:
                print('\033[31mtimeout exceeded, killing\033[0m')
                p.kill()
                p.returncode = -1
                break
        else: # got line
            print("> ", l.decode().strip())
            stdout += l.decode()
        time.sleep(0.01)

    
    print("exited as ", p.returncode)

    
    if p.returncode == 0:
        result = dict(stdout=stdout)
        status = 'success'

        print("\033[32mSUCCESS!\033[0m")
    else:
        result = dict(stdout=stdout, exception=p.returncode)
        status = 'failed'

        print("\033[31mFAILED!\033[0m")

    try:
        result['func_return'] = json.loads(re.search("^RESULT:(.*)", stdout, re.M).group(1))
    except Exception as e:
        print("no output")

    return dict(result=result, status=status)


def test_func(file, func, ref="master"):
    def _func(**kwargs):
        return run(
            dict(
                base = dict(
                    call_type="http://odahub.io/ontology#python_function",
                    call_context="http://odahub.io/ontology#python3",
                    location=f"https://raw.githubusercontent.com/volodymyrss/oda_test_kit/{ref}/{file}.py::{func}"                
                ),
                inputs=kwargs
            )
        )['result']['func_return']

    return _func