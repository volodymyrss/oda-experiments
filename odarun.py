import subprocess
import requests

import os
import re

class UnsupportedCallType(Exception):
    pass

def run(w):
    print("run this", w)

    if w['base']['call_type'] == "http://odahub.io/ontology#python_function" \
        and w['base']['call_context'] == "http://odahub.io/ontology#python3":
            return run_python_function(w)

    raise UnsupportedCallType("unable to run this calltype:", w['base']['call_type'])

def run_python_function(w):
    try:
        url, func = w['base']['location'].split("::")
    except Exception as e:
        raise Exception("can not split", w['base']['location'], e)

    pars = ",".join(["%s=\"%s\""%(k,v) for k,v in w['inputs'].items()])

    import subprocess

    if re.match("https://raw.githubusercontent.com/volodymyrss/oda_test_kit/+[0-9a-z]+?/test_[a-z0-9]+?.py", url):
        print("found valid url", url)
    else:
        raise Exception("invalid url: %s!"%url)
    
    if re.match("test_[a-z0-9]+?", func):
        print("found valid func:", func)
    else:
        raise Exception("invalid func: %s!"%func)


    urls = [
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
    c += "\n\n%s(%s)"%(func, pars)

    print("calling python with:\n", "\n>".join(c.split("\n")))

    p = subprocess.Popen(["python"], 
                            stdin=subprocess.PIPE, 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.STDOUT, 
                            env={**os.environ, "PYTHONUNBUFFERED":"1"},
                            bufsize=0)

    p.stdin.write(c.encode())

    p.stdin.close()

    stdout = ""
    for l in p.stdout:
        print("> ", l.decode().strip())
        stdout += l.decode()
    
    p.wait()

    print("exited as ", p.returncode)

    
    if p.returncode == 0:
        result = dict(stdout=stdout)
        status = 'success'
    else:
        result = dict(stdout=stdout, exception=p.returncode)
        status = 'failed'


    return dict(result=result, status=status)
