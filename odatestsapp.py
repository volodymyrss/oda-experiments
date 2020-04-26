from flask import Flask
from flask import render_template,make_response,request,jsonify

import pprint

from odaworkflow import validate_workflow, w2uri

import requests

import hashlib
import copy

import rdflib

import peewee
import datetime
import yaml
import io

import subprocess

import functools

from flask_jwt import JWT, jwt_required, current_identity
from werkzeug.security import safe_str_cmp

from urllib.parse import urlencode, quote_plus

import odakb
import odakb.sparql
import odakb.datalake

from odakb.sparql import init as rdf_init
from odakb.sparql import nuri

import os
import time
import socket
from hashlib import sha224
from collections import OrderedDict, defaultdict
import glob
import logging

import odarun

import jsonschema
import json

from typing import Union
from odakb.sparql import render_uri, nuri
import odakb.sparql 

odakb.sparql.stop_stats_collection()

import pymysql
import peewee
from playhouse.db_url import connect
from playhouse.shortcuts import model_to_dict, dict_to_model

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



def assertEqual(a, b, e=None):
    if a != b:
        raise Exception("%s != %s"%(a,b))

def authenticate(username, password):
    user = username_table.get(username, None)
    if user and safe_str_cmp(user.password.encode('utf-8'), password.encode('utf-8')):
        return user

def identity(payload):
    user_id = payload['identity']
    return userid_table.get(user_id, None)



n_failed_retries = int(os.environ.get('DQUEUE_FAILED_N_RETRY','20'))

logger=logging.getLogger(__name__)
logger.setLevel(logging.INFO)
#handler=logging.StreamHandler()
#logger.addHandler(handler)
#formatter = logging.Formatter('%(asctime)s %(levelname)8s %(name)s | %(message)s')
#handler.setFormatter(formatter)

def log(*args,**kwargs):
    severity=kwargs.get('severity','warning').upper()
    logger.log(getattr(logging,severity)," ".join([repr(arg) for arg in list(args)+list(kwargs.items())]))






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

class BadRequest(Exception):
    pass

@app.errorhandler(BadRequest)
def handle_error(error):
    return make_response(str(error)), 400

@app.errorhandler(Exception)
def handle_error(error):
    raise error
    return make_response("Unexpected error. I am not sure how you made this happen, but I thank you for spotting this issue, I dealing with it! If you want to keep in touch, please share your email"), 500

@app.route("/status")
def status():
    return make_response("status is ok")

@app.route("/test-error")
def testerror():
    raise Exception("test error")

@app.route('/tests', methods=["GET"])
def tests_get():
    f = request.args.get("f", None)
    return jsonify(get_tests(f))

def add_basic_platform_test(uri, location, email, extra):
    assert uri
    assert location
    assert email

    odakb.sparql.insert(query="""
                    {uri} oda:belongsTo oda:basic_testkit . 
                    {uri} a oda:test .
                    {uri} a oda:workflow .
                    {uri} oda:callType oda:python_function .
                    {uri} oda:callContext oda:python3 .
                    {uri} oda:location {location} .
                    {uri} oda:expects oda:input_cdciplatform .
                    {uri} dc:contributor "{email}" .
                    {extra_rdf}
                    """.format(
                            uri=odakb.sparql.render_uri(uri), 
                            location=odakb.sparql.render_uri(location),
                            email=email,
                            extra_rdf=extra,
                         ))

@app.route('/coming-soon', methods=["GET"])
def coming_soon():
    return "coming soon!"

@app.route('/add-test', methods=["GET"])
def add_test_form():
    return render_template("add-form.html",
                uri=request.args.get('uri'),
                location=request.args.get('location'),
            )

@app.route('/tests', methods=["PUT"])
@app.route('/tests/add', methods=["GET"])
def tests_put():
    add_basic_platform_test(
                request.args.get('uri'),
                request.args.get('location'),
                request.args.get('submitter_email'),
                request.args.get('extra_rdf'),
            )
    return jsonify(dict(status="ok"))


@app.route('/expire', methods=["PUT", "GET"])
def expire_uri():
    odakb.sparql.insert(
                "{} oda:realm oda:expired".format(nuri(request.args.get('uri'))),
            )
    return jsonify(dict(status="ok"))



def get_tests(f=None):
    tests=[]

    for t in odakb.sparql.select(query="""
                        ?workflow oda:belongsTo oda:basic_testkit; 
                              a oda:test;
                              a oda:workflow;
                              oda:callType ?call_type;
                              oda:callContext ?call_context;
                              oda:location ?location .
                              
                        OPTIONAL { ?workflow dc:contributor ?email }

                        NOT EXISTS { ?workflow oda:realm oda:expired }

                    """ + (f or "")):
        logger.info("selected workflow entry: %s", t)


        t['domains'] = odakb.sparql.select(query="""
                        {workflow} oda:domain ?domain
                        """.format(workflow=nuri(t['workflow'])))
        
        t['expects'] = {}

        for r in odakb.sparql.select(query="""
                        <{workflow}> oda:expects ?expectation .
                        ?expectation a ?ex_type .
                        """.format(workflow=t['workflow'])):
            #if 

            binding = r['expectation'].split("#")[1][len("input_"):]

            t['expects'][binding] = r['ex_type']

        logger.info("test: \n" + pprint.pformat(t))

        tests.append(t)

    return tests


def design_goals(f=None):
    goals = []
    for test in get_tests(f):
        logger.info("goal for test: %s", test)
        for bind, ex in test['expects'].items():
            for option in odakb.sparql.select('?opt a <%s>'%ex):
                if not '#input_' in option['opt']:
                    goals.append({"base": test, 'inputs': {bind: option['opt']}}) #, 'reason': odakb.sparql.render_rdf('?opt a <%s>'%ex, option)}})

    tgoals = []
    for _g in goals:
        #tgoals.append(_g)
        g = copy.deepcopy(_g)
        g['inputs']['timestamp'] = midnight_timestamp()
        tgoals.append(g)

        g = copy.deepcopy(_g)
        g['inputs']['timestamp'] = recent_timestamp(6000)
        tgoals.append(g)

    toinsert = ""

    byuri={}
    for goal in tgoals:
        goal_uri = w2uri(goal, "goal")
        byuri[goal_uri] = goal

        toinsert += "\n {goal_uri} a oda:workflow; a oda:testgoal; oda:curryingOf {base_uri} .".format(
                    goal_uri=goal_uri,
                    base_uri=nuri(goal['base']['workflow']),
                )

    print("toinsert", toinsert[:300])

    odakb.sparql.insert(toinsert)

    bucketless = odakb.sparql.select("?goal_uri a oda:testgoal . NOT EXISTS { ?goal_uri oda:bucket ?b }", form="?goal_uri")

    toinsert = ""
    for goal_uri in [r['goal_uri'] for r in bucketless]:
        goal_uri = goal_uri.replace("http://ddahub.io/ontology/data#", "data:")

        if goal_uri not in byuri:
            logging.warning("bucketless goal %s not currently designable: ignoring", goal_uri)
            continue

        print("bucketless goal:", goal_uri)

        bucket = odakb.datalake.store(byuri[goal_uri])

        assertEqual(nuri(w2uri(byuri[goal_uri], "goal")), nuri(goal_uri))

        toinsert += "\n {goal_uri} oda:bucket \"{bucket}\" .".format(goal_uri=goal_uri, bucket=bucket)

#        reconstructed_goal = get_data(goal_uri)
#        assert nuri(w2uri(reconstructed_goal, "goal")) == goal_uri

    print("toinsert", len(toinsert))
    odakb.sparql.insert(toinsert)


    return tgoals
    
def get_goals(f="all", wf=None):
    q = """
            ?goal_uri a oda:testgoal .

            NOT EXISTS {
                ?goal_uri oda:curryingOf ?W .
                ?W oda:realm oda:expired .
            }
            """

    if f == "reached":
        q += """
            ?goal_uri oda:equalTo ?data . 
            ?data oda:bucket ?data_bucket . 
            """
    elif f == "unreached":
        q += """
             NOT EXISTS {
                 ?goal_uri oda:equalTo ?data . 
                 ?data oda:bucket ?data_bucket . 
             }
             """

    if wf is not None:
        if '?w' not in wf:
            raise BadRequest("workflow filter does not contain \"?w\" workflow variable")

        q += "?goal_uri oda:curryingOf ?w ."
        q += wf
    
    r = odakb.sparql.select(q)

    return [ u['goal_uri'] for u in r ]



@app.route('/goals')
def goals_get(methods=["GET"]):
    #odakb.sparql.reset_stats_collection()

    f = request.args.get('f', "all")

    if 'design' in request.args:
        design_goals()

    return jsonify(get_goals(f))

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


def midnight_timestamp():
    now = datetime.datetime.now()
    return datetime.datetime(now.year, now.month, now.day).timestamp()

def recent_timestamp(waittime):
    sind = datetime.datetime.now().timestamp() - midnight_timestamp()
    return midnight_timestamp() + int(sind/waittime)*waittime

@app.route('/offer-goal')
def offer_goal():
    rdf_init()

    n = request.args.get('n', 1, type=int)
    f = request.args.get('f', None) 

    r = []

    design_goals()

    unreached_goals = get_goals("unreached", wf=f)

    if len(unreached_goals) > n:
        goal_uri = unreached_goals[n]
        #goal_uri = w2uri(goal)

        print("goal to offer", goal_uri)

        goal = get_data(goal_uri)

        assertEqual(nuri(goal_uri), nuri(w2uri(goal, "goal")))

        print("offering goal", goal)
        print("offering goal uri", goal_uri)

        return jsonify(dict(goal_uri=goal_uri, goal=goal))
    else:
        return jsonify(dict(warning="no goals"))

@app.route('/report-goal', methods=["POST"])
def report_goal():
    d = request.json
    goal = d.get('goal')
    data = d.get('data')
    worker = d.get('worker')

    r = store(goal, data)

    return jsonify(r)

    #return make_response("deleted %i"%nentries)

@app.route('/evaluate')
def evaluate_one():
    skip = request.args.get('skip', 0, type=int)
    n = request.args.get('n', 1, type=int)
    f = request.args.get('f', None) 

    r = []

    for goal in get_goals("unreached")[skip:]:
        runtime_origin, value = evaluate(goal)

        if runtime_origin != "restored":
            r.append(dict(
                    workflow = goal,
                    value = value,
                    runtime_origin = runtime_origin,
                    uri = w2uri(goal),
                ))

        if len(r) >= n:
            break

    return jsonify(dict(goal_uri=w2uri(goal, "goal"), goal=r))
    #return make_response("deleted %i"%nentries)

def list_data(f=None):
    r = odakb.sparql.select("""
            ?data oda:curryingOf ?workflow; 
                  ?input_binding ?input_value;
                  oda:test_status ?test_status .


            ?input_binding a oda:curried_input .

            ?workflow a oda:test; 
                      oda:belongsTo oda:basic_testkit .

            OPTIONAL {
                ?workflow oda:domain ?workflow_domains 
            }

            NOT EXISTS { ?data oda:realm oda:expired }
            NOT EXISTS { ?workflow oda:realm oda:expired }

                      """+(f or ""))


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
        
        for joined_key in "workflow_domains",:
            l = [ve[joined_key] for ve in v if joined_key in ve]
            R[joined_key] = list(set(l))
             
        R['inputs'] = {}
        for ve in v:
            R['inputs'][ve['input_binding']] = input_value=ve['input_value']
            if ve['input_binding'] == "http://odahub.io/ontology#curryied_input_timestamp":
                R['timestamp'] = float(ve['input_value'])
                R['timestamp_age_h'] = (time.time() - R['timestamp'])/3600.

        R['inputs'] = [dict(input_binding=k, input_value=v) for k,v in R['inputs'].items()]




    return sorted(result, key=lambda x:-x.get('timestamp',0))

def get_data(uri):
    r = odakb.sparql.select_one("""
            {data} oda:bucket ?bucket . 
                     """.format(data=odakb.sparql.render_uri(uri)))

    b = odakb.datalake.restore(r['bucket'])

    return b

def get_graph(uri):
    r =  [ "{s} {p} {uri}".format(uri=uri, **l)
           for l in odakb.sparql.select("?s ?p {}".format(odakb.sparql.render_uri(uri))) ]
    r += [ "{uri} {p} {o}".format(uri=uri, **l)
           for l in odakb.sparql.select("{} ?p ?o".format(odakb.sparql.render_uri(uri))) ]
    r += [ "{s} {uri} {o}".format(uri=uri, **l)
           for l in odakb.sparql.select("?s {} ?o".format(odakb.sparql.render_uri(uri))) ]

    r = map(odakb.sparql.render_rdf, r)
    #r = [" ".join([odakb.sparql.render_uri(u) for u in _r.split(None, 2)]) for _r in r]

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

def list_features():
    fs = odakb.sparql.select("""
                ?ft a oda:feature;
                    oda:descr ?descr;
                    oda:provenBy ?w;
                    ?p ?o .

                ?w a oda:test .

                NOT EXISTS { ?w oda:realm oda:expired }
            """, "?ft ?p ?o", tojdict=True)

    return fs

@app.route('/features')
def features():
    fs = list_features()

    if 'json' in request.args:
        return jsonify(fs)

    return render_template("features.html", features=fs)

@app.route('/workflow')
def workflow():
    uri = request.args.get("uri")

    if 'json' in request.args:
        if uri:
            return jsonify(describe_workflow(uri))
        else:
            return jsonify(dict(status="missing uri"))

    if uri:
        return render_template("workflow.html", w=describe_workflow(uri))
    else:
        return jsonify(dict(status="missing uri"))

@app.route('/workflows')
def workflows():
    workflows = get_tests()

    if 'json' in request.args:
        return jsonify(workflows)
    else:
        return render_template("workflows.html", data=workflows)

@app.route('/graph')
def graph():
    totable = "table" in request.args
    tordf = "rdf" in request.args

    uri = request.args.get("uri")
    if uri:
        g = get_graph(uri)

        print("graph for", uri, g)

        if totable:
            return jsonify(g)
        elif tordf:
            G = rdflib.Graph().parse(data=odakb.sparql.tuple_list_to_turtle(g), format='turtle')

            rdf = G.serialize(format='turtle').decode()

            return rdf, 200
        else:
            G = rdflib.Graph().parse(data=odakb.sparql.tuple_list_to_turtle(g), format='turtle')

            jsonld = G.serialize(format='json-ld', indent=4, sort_keys=True).decode()

            return jsonify(json.loads(jsonld))
    else:
        return jsonify(dict(status="missing uri"))

@app.route('/data')
def viewdata():
    uri = request.args.get("uri")
    if uri:
        return jsonify(get_data(uri))

    if 'json' in request.args:
        return jsonify(list_data())

    f = request.args.get("f", None)

    odakb.sparql.reset_stats_collection()
    d = list_data(f)
    request_stats = odakb.sparql.query_stats
    odakb.sparql.stop_stats_collection()

    if len(d)>0:
        domains = set(functools.reduce(lambda x,y:x+y, [R.get('workflow_domains', []) for R in d]))
    else:
        domains = []

    r = render_template('data.html', 
                domains=domains,
                data=d, 
                request_stats=request_stats,
                timestamp_now=time.time()
            )



    return r

@app.route('/')
def viewdash():
    r = render_template('dashboard.html')
    return r

@app.template_filter()
def uri(uri):
    suri = uri.replace("http://odahub.io/ontology#", "oda:")

    return '<a href="graph?uri={}">{}</a>'.format(quote_plus(uri), suri)

@app.template_filter()
def locurl(uri):
    if "::" in uri:
        url, anc = uri.split("::")
    else:
        url, anc = uri, ""

    commit, fn = url.split("/")[-2:]
    surl = commit[:8]+"/"+fn

    return '<a href="{url}#{anc}">{surl}::{anc}</a>'.format(url=url, anc=anc, surl=surl)


def evaluate(w: Union[str, dict], allow_run=True):
    goal_uri = None
    if isinstance(w, str):
        goal_uri = w
        b = odakb.sparql.select_one("{} oda:bucket ?b".format(render_uri(w)))['b']
        w = odakb.datalake.restore(b)

    jsonschema.validate(w, json.loads(open("workflow-schema.json").read()))

    print("evaluate this", w)


    r = restore(w) 

    if r is not None:
        return 'restored', r
    else:
        
        if allow_run:
            r = { 'origin':"run", **odarun.run(w)}

            s = store(w, r)
        
            if nuri(s['goal_uri']) != nuri(goal_uri):
                print("stored goal uri", s['goal_uri'])
                print("requested goal uri", goal_uri)
                raise Exception("inconsistent storage")

            return 'ran', r
        else:
            return None



def store(w, d):
    uri = w2uri(w)
    goal_uri = w2uri(w, "goal")

    print("storing", d)

    b = odakb.datalake.store(dict(data=d, workflow=w))
    s="""
            {goal_uri} oda:equalTo {data_uri} .
            {data_uri} oda:location oda:minioBucket;
                       oda:bucket \"{bucket_name}\";
                       oda:curryingOf <{base_workflow}>;
                       oda:test_status oda:{status}""".format(
                                data_uri=uri,
                                goal_uri=goal_uri,
                                base_workflow=w['base']['workflow'],
                                bucket_name=b,
                                status=d['status']
                            )

    print("created, to insert:", s)

    odakb.sparql.insert(s)

    for k, v in w['inputs'].items():
        odakb.sparql.insert("%s oda:curryied_input_%s \"%s\""%(uri, k, v))
        odakb.sparql.insert("oda:curryied_input_%s a oda:curried_input"%(k))

    return dict(goal_uri=goal_uri, uri=uri, bucket=b)

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


def listen(args):
    app.run(port=5555,debug=True,host=args.host,threaded=True)
    
