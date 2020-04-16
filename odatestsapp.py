from flask import Flask
from flask import render_template,make_response,request,jsonify

import pprint

import hashlib
import copy

import peewee
import datetime
import yaml
import io

import subprocess

from flask_jwt import JWT, jwt_required, current_identity
from werkzeug.security import safe_str_cmp


import odakb

import os
import time
import socket
from hashlib import sha224
from collections import OrderedDict, defaultdict
import glob
import logging

try:
    import io
except:
    from io import StringIO

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse


class User(object):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

    def __str__(self):
        return "User(id='%s')" % self.id

users = [
    User(1, 'testbot', os.environ.get("ODATESTS_BOT_PASSWORD")),
]

username_table = {u.username: u for u in users}
userid_table = {u.id: u for u in users}

def authenticate(username, password):
    user = username_table.get(username, None)
    if user and safe_str_cmp(user.password.encode('utf-8'), password.encode('utf-8')):
        return user

def identity(payload):
    user_id = payload['identity']
    return userid_table.get(user_id, None)


import pymysql
import peewee
from playhouse.db_url import connect
from playhouse.shortcuts import model_to_dict, dict_to_model

n_failed_retries = int(os.environ.get('DQUEUE_FAILED_N_RETRY','20'))

logger=logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler=logging.StreamHandler()
logger.addHandler(handler)
formatter = logging.Formatter('%(asctime)s %(levelname)8s %(name)s | %(message)s')
handler.setFormatter(formatter)

def log(*args,**kwargs):
    severity=kwargs.get('severity','warning').upper()
    logger.log(getattr(logging,severity)," ".join([repr(arg) for arg in list(args)+list(kwargs.items())]))


def connect_db():
    return connect(os.environ.get("DQUEUE_DATABASE_URL","mysql+pool://root@localhost/dqueue?max_connections=42&stale_timeout=8001.2"))

try:
    db=connect_db()
except:
    pass


class TestResult(peewee.Model):
    key = peewee.CharField(primary_key=True)

    result = peewee.CharField()
    created = peewee.DateTimeField()

    component = peewee.CharField()
    deployment = peewee.CharField()
    endpoint = peewee.CharField()

    entry = peewee.TextField()


    class Meta:
        database = db

try:
    db.create_tables([TestResult])
    has_mysql = True
except peewee.OperationalError:
    has_mysql = False
except Exception:
    has_mysql = False











try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse


from playhouse.db_url import connect
from playhouse.shortcuts import model_to_dict, dict_to_model


decoded_entries={}


class ReverseProxied(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_FORWARDED_PREFIX', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ['PATH_INFO']
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

        scheme = environ.get('HTTP_X_SCHEME', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)

def create_app():
    app = Flask(__name__)
    app.wsgi_app = ReverseProxied(app.wsgi_app)
    app.debug = True
    app.config['SECRET_KEY'] = os.environ.get("ODATESTS_SECRET_KEY")

    jwt = JWT(app, authenticate, identity)
    return app

app = create_app()

@app.route('/tests', methods=["GET"])
def tests_get():
    return jsonify(get_tests())

def add_basic_platform_test(uri, location):
    assert uri
    assert location

    odakb.sparql.insert(query="""
                    {uri} oda:belongsTo oda:basic_testkit . 
                    {uri} a oda:test .
                    {uri} a oda:workflow .
                    {uri} oda:callType oda:python_function .
                    {uri} oda:callContext oda:python3 .
                    {uri} oda:location {location} .
                    {uri} oda:expects oda:input_cdciplatform .
                    """.format(
                            uri=odakb.sparql.render_uri(uri), 
                            location=odakb.sparql.render_uri(location)
                         ))


@app.route('/tests', methods=["PUT"])
def tests_put():
    add_basic_platform_test(
                request.args.get('uri'),
                request.args.get('location'),
            )
    return jsonify(dict(status="ok"))

def get_tests():
    tests=[]

    for t in odakb.sparql.select(query="""
                    ?workflow oda:belongsTo oda:basic_testkit; 
                          a oda:test;
                          a oda:workflow;
                          oda:callType ?call_type;
                          oda:callContext ?call_context;
                          oda:location ?location
                    """):


        t['expects'] = {}

        for r in odakb.sparql.select(query="""
                        <%s> oda:expects ?expectation .
                        ?expectation a ?ex_type
                        """%t['workflow']):

            binding = r['expectation'].split("#")[1][len("input_"):]

            t['expects'][binding] = r['ex_type']

        logger.info("test: \n" + pprint.pformat(t))

        tests.append(t)

    return tests


def get_goals():
    goals = []
    for test in get_tests():
        for bind, ex in test['expects'].items():
            for option in odakb.sparql.select('?opt a <%s>'%ex):
                goals.append({"base": test, 'inputs': {bind: option['opt']}})

    tgoals = []
    for _g in goals:
        tgoals.append(_g)
        g = copy.deepcopy(_g)
        g['inputs']['timestamp'] = midnight_timestamp()
        tgoals.append(g)

    return tgoals

@app.route('/goals')
def goals_get(methods=["GET"]):
    return jsonify(get_goals())

@app.route('/test-results')
def test_results_get(methods=["GET"]):
    try:
        db.connect()
    except peewee.OperationalError as e:
        pass

    decode = bool(request.args.get('raw'))

    print("searching for entries")
    date_N_days_ago = datetime.datetime.now() - datetime.timedelta(days=float(request.args.get('since',1)))

    entries=[entry for entry in TestResult.select().where(Test.modified >= date_N_days_ago).order_by(Test.modified.desc()).execute()]

    bystate = defaultdict(int)
    #bystate = defaultdict(list)

    for entry in entries:
        print("found state", entry.state)
        bystate[entry.state] += 1
        #bystate[entry.state].append(entry)

    db.close()

    if request.args.get('json') is not None:
        return jsonify({k:v for k,v in bystate.items()})
    else:
        return render_template('task_stats.html', bystate=bystate)
    #return jsonify({k:len(v) for k,v in bystate.items()})

@app.route('/tests', methods=["POST"])
@jwt_required()
def tests_post():
    try:
        db.connect()
    except peewee.OperationalError as e:
        pass

    return jsonify({})




@app.route('/stats')
def stats():
    try:
        db.connect()
    except peewee.OperationalError as e:
        pass

    decode = bool(request.args.get('raw'))

    print("searching for entries")
    date_N_days_ago = datetime.datetime.now() - datetime.timedelta(days=float(request.args.get('since',1)))

    entries=[entry for entry in TestResult.select().where(Test.modified >= date_N_days_ago).order_by(Test.modified.desc()).execute()]

    bystate = defaultdict(int)
    #bystate = defaultdict(list)

    for entry in entries:
        print("found state", entry.state)
        bystate[entry.state] += 1
        #bystate[entry.state].append(entry)

    db.close()

    if request.args.get('json') is not None:
        return jsonify({k:v for k,v in bystate.items()})
    else:
        return render_template('task_stats.html', bystate=bystate)
    #return jsonify({k:len(v) for k,v in bystate.items()})

@app.route('/list')
def list_entries():
    try:
        db.connect()
    except peewee.OperationalError as e:
        pass


    pick_state = request.args.get('state', 'any')

    json_filter = request.args.get('json_filter')

    decode = bool(request.args.get('raw'))

    print("searching for entries")
    date_N_days_ago = datetime.datetime.now() - datetime.timedelta(days=float(request.args.get('since',1)))

    if pick_state != "any":
        if json_filter:
            entries=[model_to_dict(entry) for entry in TestResult.select().where((Test.state == pick_state) & (Test.modified >= date_N_days_ago) & (Test.entry.contains(json_filter))).order_by(Test.modified.desc()).execute()]
        else:
            entries=[model_to_dict(entry) for entry in TestResult.select().where((Test.state == pick_state) & (Test.modified >= date_N_days_ago)).order_by(Test.modified.desc()).execute()]
    else:
        if json_filter:
            entries=[model_to_dict(entry) for entry in TestResult.select().where((Test.modified >= date_N_days_ago) & (Test.entry.contains(json_filter))).order_by(Test.modified.desc()).execute()]
        else:
            entries=[model_to_dict(entry) for entry in TestResult.select().where(Test.modified >= date_N_days_ago).order_by(Test.modified.desc()).execute()]


    print(("found entries",len(entries)))
    for entry in entries:
        print(("decoding",len(entry['entry'])))
        if entry['entry'] in decoded_entries:
            entry_data=decoded_entries[entry['entry']]
        else:
            try:
                entry_data=yaml.load(io.StringIO(entry['entry']))
                entry_data['submission_info']['callback_parameters']={}
                for callback in entry_data['submission_info']['callbacks']:
                    if callback is not None:
                        entry_data['submission_info']['callback_parameters'].update(urlparse.parse_qs(callback.split("?",1)[1]))
                    else:
                        entry_data['submission_info']['callback_parameters'].update(dict(job_id="unset",session_id="unset"))
            except Exception as e:
                raise
                print("problem decoding", repr(e))
                entry_data={'task_data':
                                {'object_identity':
                                    {'factory_name':'??'}},
                            'submission_info':
                                {'callback_parameters':
                                    {'job_id':['??'],
                                     'session_id':['??']}}
                            }


            decoded_entries[entry['entry']]=entry_data
        entry['entry']=entry_data

    db.close()
    return render_template('task_list.html', entries=entries)

@app.route('/task/info/<string:key>')
def task_info(key):
    entry=[model_to_dict(entry) for entry in TestResult.select().where(Test.key==key).execute()]
    if len(entry)==0:
        return make_response("no such entry found")

    entry=entry[0]

    print(("decoding",len(entry['entry'])))

    try:
        entry_data=yaml.load(io.StringIO(entry['entry']))
        entry['entry']=entry_data
            
        from ansi2html import ansi2html

        if entry['entry']['execution_info'] is not None:
            entry['exception']=entry['entry']['execution_info']['exception']['exception_message']
            formatted_exception=ansi2html(entry['entry']['execution_info']['exception']['formatted_exception']).split("\n")
        else:
            entry['exception']="no exception"
            formatted_exception=["no exception"]
        
        history=[model_to_dict(en) for en in TaskHistory.select().where(TaskHistory.key==key).order_by(TaskHistory.id.desc()).execute()]
        #history=[model_to_dict(en) for en in TaskHistory.select().where(TaskHistory.key==key).order_by(TaskHistory.timestamp.desc()).execute()]

        r = render_template('task_info.html', entry=entry,history=history,formatted_exception=formatted_exception)
    except:
        r = jsonify(entry['entry'])

    db.close()
    return r

@app.route('/purge')
def purge():
    nentries=TestResult.delete().execute()
    return make_response("deleted %i"%nentries)

@app.route('/resubmit/<string:scope>/<string:selector>')
def resubmit(scope,selector):
    if scope=="state":
        if selector=="all":
            nentries=TestResult.update({
                            TestResult.state:"waiting",
                            TestResult.modified:datetime.datetime.now(),
                        })\
                        .execute()
        else:
            nentries=TestResult.update({
                            TestResult.state:"waiting",
                            TestResult.modified:datetime.datetime.now(),
                        })\
                        .where(TestResult.state==selector)\
                        .execute()
    elif scope=="task":
        nentries=TestResult.update({
                        TestResult.state:"waiting",
                        TestResult.modified:datetime.datetime.now(),
                    })\
                    .where(TestResult.key==selector)\
                    .execute()

    return make_response("resubmitted %i"%nentries)


#         class MyApplication(Application):
#            def load(self):

#                  from openlibrary.coverstore import server, code
#                   server.load_config(configfile)
#                    return code.app.wsgifunc()


def midnight_timestamp():
    now = datetime.datetime.now()
    return datetime.datetime(now.year, now.month, now.day).timestamp()

@app.route('/evaluate')
def evaluate_one():
    skip = request.args.get('skip', 0, type=int)
    n = request.args.get('n', 1, type=int)

    r = []

    for goal in get_goals()[skip:skip+n]:
        runtime_origin, value = evaluate(goal)
        r.append(dict(
                workflow = goal,
                value = value,
                runtime_origin = runtime_origin,
                uri = w2uri(goal),
            ))

    return jsonify(r)
    #return make_response("deleted %i"%nentries)

def list_data():
    r = odakb.sparql.select("""
            ?data oda:curryingOf ?workflow; 
                  ?input_binding ?input_value;
                  oda:test_status ?test_status .

            ?input_binding a oda:curried_input .

            ?workflow a oda:test; 
                      oda:belongsTo oda:basic_testkit .""")

    bydata = defaultdict(list)
    for d in r:
        bydata[d['data']].append(d)

    result = []
    for k, v in bydata.items():
        R={}
        result.append(R)

        R['uri'] = k

        for common_key in "test_status", "workflow":
            l = [ve[common_key] for ve in v]
            assert all([_l==l[0] for _l in l])
            R[common_key] = l[0]
             
        R['inputs'] = []
        for ve in v:
            R['inputs'].append(dict(input_binding=ve['input_binding'], input_value=ve['input_value']))


    return result

def get_data(uri):
    r = odakb.sparql.select_one("""
            {data} oda:bucket ?bucket . 
                     """.format(data=odakb.sparql.render_uri(uri)))

    b = odakb.datalake.restore(r['bucket'])

    return b

def get_graph(uri):
    r = [ "{s} {p} {uri}".format(uri=uri, **l)
           for l in odakb.sparql.select("?s ?p {}".format(odakb.sparql.render_uri(uri))) ]
    r += [ "{uri} {p} {o}".format(uri=uri, **l)
           for l in odakb.sparql.select("{} ?p ?o".format(odakb.sparql.render_uri(uri))) ]
    r += [ "{s} {uri} {o}".format(uri=uri, **l)
           for l in odakb.sparql.select("?s {} ?o".format(odakb.sparql.render_uri(uri))) ]

    return r


def describe_workflow(uri):
    ts = odakb.sparql.select(query="""
                    {uri} a oda:workflow;
                          ?p ?o .
                    """.format(uri=odakb.sparql.render_uri(uri)))

    r={}
    w=dict(uri=uri, relations=r)

    for t in ts:
        r[t['p']] = t['o']

        if t['p'] == "http://odahub.io/ontology#location": # viewers by class
            w['location'], w['function'] = t['o'].split("::")

    return w

@app.route('/workflow')
def workflow():
    uri = request.args.get("uri")
    if uri:
        return jsonify(describe_workflow(uri))
    else:
        return jsonify(dict(status="missing uri"))

@app.route('/view-workflow')
def viewworkflow():
    uri = request.args.get("uri")
    if uri:
        return render_template("view-workflow.html", w=describe_workflow(uri))
    else:
        return jsonify(dict(status="missing uri"))

@app.route('/graph')
def graph():
    uri = request.args.get("uri")
    if uri:
        return jsonify(get_graph(uri))
    else:
        return jsonify(dict(status="missing uri"))

@app.route('/data')
def data():
    uri = request.args.get("uri")
    if uri:
        return jsonify(get_data(uri))
    else:
        return jsonify(list_data())

@app.route('/view-data')
def viewdata():
    return render_template('view-data.html', data=list_data())



#from gunicorn.app.base import Application
#Application().run(app,port=5555,debug=True,host=args.host)

#       MyApplication().run()

# to oda-kb, or better runner

import jsonschema
import json

def evaluate(w):
    jsonschema.validate(w, json.loads(open("workflow-schema.json").read()))

    print("evaluate this", w)


    r = restore(w) 

    if r is not None:
        return 'restored', r
    else:
        try:
            r = dict(status='success', origin="run", result = run(w))
        except Exception as e:
            r = dict(status='failure', origin="run", exception = repr(e))

        store(w, r)
        return 'ran', r


def w2uri(w):
    return "data:w-"+hashlib.sha256(json.dumps(w).encode()).hexdigest()[:16]

def store(w, d):
    uri = w2uri(w)

    b = odakb.datalake.store(dict(data=d, workflow=w))
    odakb.sparql.insert("%s oda:location oda:minioBucket"%(uri))
    odakb.sparql.insert("%s oda:bucket \"%s\""%(uri, b))
    odakb.sparql.insert("%s oda:curryingOf <%s>"%(uri, w['base']['workflow']))
    odakb.sparql.insert("%s oda:test_status oda:%s"%(uri, d['status']))

    for k, v in w['inputs'].items():
        odakb.sparql.insert("%s oda:curryied_input_%s \"%s\""%(uri, k, v))
        odakb.sparql.insert("oda:curryied_input_%s a oda:curried_input"%(k))

def restore(w):
    uri = w2uri(w)

    try:
        r = odakb.sparql.select_one("%s oda:bucket ?bucket"%odakb.sparql.render_uri(uri, {}))

        b = odakb.datalake.restore(r['bucket'])

        return b['data']

    except odakb.sparql.NoAnswers:
        print("not known: %s"%uri)
        return None

    except odakb.sparql.ManyAnswers:
        print("ambigiously known: %s"%uri)
        return None

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
        stdout = subprocess.check_output(['bash', '-c', c]).decode()
    except Exception as e:
        pass

    return dict(stdout=stdout)


def listen(args):
    app.run(port=5555,debug=True,host=args.host,threaded=True)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("queue",default="./queue")
    parser.add_argument('-L', dest='listen',  help='...',action='store_true', default=False)
    parser.add_argument('-H', dest='host',  help='...', default="0.0.0.0")
    args=parser.parse_args()

    listen(args)
