def run(w):
    print("run this", w)

    if w['base']['call_type'] == "http://odahub.io/ontology#python_function" \
       and w['base']['call_context'] == "http://odahub.io/ontology#python3":
        return run_python_function(w)

def run_python_function(w):
    try:
        url, func = w['base']['location'].split("::")
    except Exception as e:
        raise Exception("can not split", w['base']['location'], e)

    pars = ",".join(["%s=\"%s\""%(k,v) for k,v in w['inputs'].items()])

    c = "curl %s  | awk 'END {print \"%s(%s)\"} 1' | python -"%(url, func, pars.replace("\"", "\\\"")) 
    print(c)

    try:
        result = dict(stdout=subprocess.check_output(['bash', '-c', c], stderr=subprocess.STDOUT).decode())
        status = 'success'
    except Exception as e:
        result = dict(stdout=e.output.decode(), exception=repr(e))
        status = 'failed'

    return dict(result=result, status=status)
