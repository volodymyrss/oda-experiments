from flask import Flask
from flask import render_template,make_response,request,jsonify, send_from_directory, url_for


import pprint
import click
import copy

from odaworkflow import validate_workflow, w2uri

import requests

import hashlib
import copy

import rdflib # type: ignore

import datetime
import yaml
import io

from ansi2html import ansi2html

import subprocess

import functools

from flask_jwt import JWT, jwt_required, current_identity # type: ignore
from werkzeug.security import safe_str_cmp

from urllib.parse import urlencode, quote_plus

import odakb # type: ignore
import odakb.sparql # type: ignore
import odakb.datalake # type: ignore
from odakb.sparql import render_uri, nuri # type: ignore
from odakb.sparql import init as rdf_init

import os
import time
import socket
from hashlib import sha224
from collections import OrderedDict, defaultdict
import glob
import logging

import odarun

import jsonschema # type: ignore
import json

from typing import Union, List


import pylogstash # type: ignore

odakb.sparql.query_stats = None

debug=True

try:
    import io
except:
    from io import StringIO

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

custom_timestamps = [] # type: List

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

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
#handler=logging.StreamHandler()
#logger.addHandler(handler)
#formatter = logging.Formatter('%(asctime)s %(levelname)8s %(name)s | %(message)s')
#handler.setFormatter(formatter)

def log(*args,**kwargs):
    severity=kwargs.get('severity','warning').upper()
    logger.info(getattr(logging,severity)," ".join([repr(arg) for arg in list(args)+list(kwargs.items())]))






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
    app.config["APPLICATION_ROOT"] = "/odatests"

    jwt = JWT(app, authenticate, identity)
    return app

app = create_app()

@app.template_filter('ansi2html')
def ansi2html_filter(arg):
    return "<br>".join(ansi2html(arg).split("\n"))

class BadRequest(Exception):
    pass

@app.errorhandler(BadRequest)
def handle_error(error):
    return make_response(str(error)), 400

@app.errorhandler(Exception)
def handle_bad_error(error):
    if debug:
        raise error
    else:
        return make_response("Unexpected error. I am not sure how you made this happen, but I thank you for spotting this issue, I dealing with it! If you want to keep in touch, please share your email"), 500

@app.route("/status")
def status():
    log_request()
    return make_response("status is ok")

@app.route("/test-error")
def testerror():
    raise Exception("test error")

@app.route('/tests', methods=["GET"])
def tests_get():
    log_request()
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
    log_request()
    return "coming soon!"

@app.route('/add-test', methods=["GET"])
def add_test_form():
    log_request()
    return render_template("add-form.html",
                uri=request.args.get('uri'),
                location=request.args.get('location'),
            )

@app.route('/tests', methods=["PUT"])
@app.route('/tests/add', methods=["GET"])
def tests_put():
    log_request()
    add_basic_platform_test(
                request.args.get('uri'),
                request.args.get('location'),
                request.args.get('submitter_email'),
                request.args.get('extra_rdf'),
            )
    return jsonify(dict(status="ok"))

@app.route('/now', methods=["PUT", "GET"])
def now():
    tslast = max(relevant_timestamps())

    t0 = int(time.time())
    
    tlim = 600

    if t0 - tslast < tlim:
        return jsonify(dict(status="NOK", message=f"too soon, {t0 - tslast} < {tlim}"))

    custom_timestamps.append(t0)
    return jsonify(dict(status="ok"))

@app.route('/moments', methods=["GET"])
def moments():
    return jsonify(dict(status="ok", relevant_timestamps=relevant_timestamps()))

def expire(u):
    odakb.sparql.insert(
                "{} oda:realm oda:expired".format(nuri(u)),
            )

@app.route('/expire', methods=["PUT", "GET"])
def expire_uri():
    log_request()
    expire(request.args.get('uri'))
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

        one_test_goals = [{
                            "base": test, 
                            'inputs': {}
                         }]

        for bind, ex in test['expects'].items(): # matrix over options
            newoption_test_goals = []

            for test_goal in one_test_goals:
                for option in odakb.sparql.select('?opt a <%s>'%ex):
                    if not '#input_' in option['opt']: # actual option, not input
                        g = copy.deepcopy(test_goal)
                        g['inputs'][bind] = option['opt']

                        newoption_test_goals.append(g)
                        #, 'reason': odakb.sparql.render_rdf('?opt a <%s>'%ex, option)}})

            one_test_goals = newoption_test_goals

        goals += one_test_goals

    tgoals = []
    for _g in goals:
        #tgoals.append(_g)

        for timestamp in relevant_timestamps(1):
            g = copy.deepcopy(_g)
            g['inputs']['timestamp'] = timestamp
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

    logger.info("toinsert", toinsert[:300])

    odakb.sparql.insert(toinsert)

    bucketless = odakb.sparql.select("?goal_uri a oda:testgoal . NOT EXISTS { ?goal_uri oda:bucket ?b }", form="?goal_uri")

    toinsert = ""
    for goal_uri in [r['goal_uri'] for r in bucketless]:
        goal_uri = goal_uri.replace("http://ddahub.io/ontology/data#", "data:")

        if goal_uri not in byuri:
            logging.warning("bucketless goal %s not currently designable: ignoring", goal_uri)
            continue

        logger.info(f"bucketless goal: {goal_uri}")

        bucket = odakb.datalake.store(byuri[goal_uri])

        assertEqual(nuri(w2uri(byuri[goal_uri], "goal")), nuri(goal_uri))

        toinsert += "\n {goal_uri} oda:bucket \"{bucket}\" .".format(goal_uri=goal_uri, bucket=bucket)

#        reconstructed_goal = get_data(goal_uri)
#        assert nuri(w2uri(reconstructed_goal, "goal")) == goal_uri

    logger.info(f"toinsert {len(toinsert)}")
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
        if '?w' not in wf and '?data' not in wf:
            raise BadRequest("workflow filter does not contain \"?w\" of \"?data\"  variables")

        q += "?goal_uri oda:curryingOf ?w ."
        q += wf
    
    try:
        r = odakb.sparql.select(q)
    except odakb.sparql.NoAnswers:
        return []

    return [ u['goal_uri'] for u in r ]



@app.route('/goals')
def goals_get(methods=["GET"]):
    log_request()
    odakb.sparql.query_stats = None

    f = request.args.get('f', "all")

    if 'design' in request.args:
        design_goals()

    return jsonify(get_goals(f))


def midnight_timestamp():
    now = datetime.datetime.now()
    return datetime.datetime(now.year, now.month, now.day).timestamp()

def recent_timestamp(waittime):
    sind = datetime.datetime.now().timestamp() - midnight_timestamp()
    return midnight_timestamp() + int(sind/waittime)*waittime

def custom_timestamp(waittime):
    sind = datetime.datetime.now().timestamp() - midnight_timestamp()
    return midnight_timestamp() + int(sind/waittime)*waittime

def relevant_timestamps(nlast=100):
    ts = []

    ts.append(midnight_timestamp())
    ts.append(recent_timestamp(3600*8))
    ts += custom_timestamps

    return list(sorted(ts))[-nlast:]

@app.route('/offer-goal')
def offer_goal():
    log_request()
    rdf_init()

    n = request.args.get('n', 1, type=int)
    f = request.args.get('f', None) 


    while True:
        r = []
        design_goals()

        unreached_goals = get_goals("unreached", wf=f)

        if len(unreached_goals) > n:
            goal_uri = unreached_goals[n]
            #goal_uri = w2uri(goal)

            logger.info("goal to offer", goal_uri)

            try:
                goal = get_data(goal_uri)
            except odakb.sparql.NoAnswers as e:
                logger.info(f"non-existent goal {goal_uri}")
                odakb.sparql.delete(f"<{goal_uri}> ?p ?o", all_entries=True)
                continue

            assertEqual(nuri(goal_uri), nuri(w2uri(goal, "goal")))

            logger.info(f"offering goal {goal}")
            logger.info(f"offering goal uri {goal_uri}")

            return jsonify(dict(goal_uri=goal_uri, goal=goal))
        else:
            return jsonify(dict(warning="no goals"))

@app.route('/report-goal', methods=["POST"])
def report_goal():
    log_request()
    d = request.json
    goal = d.get('goal')
    data = d.get('data')
    worker = d.get('worker')

    r = store(goal, data)

    return jsonify(r)

    #return make_response("deleted %i"%nentries)

@app.route('/evaluate')
def evaluate_one():
    log_request()
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

def get_timestamps(f=None):
    r = odakb.sparql.select("""
            ?data oda:curryingOf ?workflow; 
                  oda:curryied_input_timestamp ?input_timestamp .

            ?workflow a oda:test; 
                      oda:belongsTo oda:basic_testkit .

            NOT EXISTS { ?data oda:realm oda:expired }
            NOT EXISTS { ?workflow oda:realm oda:expired }

                      """+(f or ""),
                      only="?input_timestamp"
                      )
    ts = [(float(d['input_timestamp']), d['input_timestamp']) for d in r]

    logger.info(ts)

    return ts

def list_data(f=None):
    ts_recent = get_timestamps()[-3:]

    r = []

    for tsi, ts in ts_recent:
        r += odakb.sparql.select(f"""
            ?data oda:curryingOf ?workflow; 
                  ?input_binding ?input_value;
                  oda:curryied_input_timestamp "{ts}";
                  oda:test_status ?test_status .


            ?input_binding a oda:curried_input .

            ?workflow a oda:test; 
                      oda:belongsTo oda:basic_testkit .

            OPTIONAL {{
                ?workflow oda:domain ?workflow_domains 
            }}

            NOT EXISTS {{ ?data oda:realm oda:expired }}
            NOT EXISTS {{ ?workflow oda:realm oda:expired }}
            
            { f or "" }
                      """)

    logger.info(f"found {len(r)} entries")


    bydata = defaultdict(list)
    for d in r:
        bydata[d['data']].append(d)

    result = []
    for k, v in bydata.items():
        R={}
        result.append(R)

        R['uri'] = k

        for common_key in "test_status", "workflow":
            l = list(set([ve[common_key] for ve in v]))
            if len(l) == 1:
                R[common_key] = l[0]
            else:
                logger.error(f"data {k} has different common key {common_key}: {l}; expiring!")
                expire(k)
        
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
    log_request()
    fs = list_features()

    if 'json' in request.args:
        return jsonify(fs)

    return render_template("features.html", features=fs)

@app.route('/workflow')
def workflow():
    log_request()
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
    log_request()
    workflows = get_tests()

    if 'json' in request.args:
        return jsonify(workflows)
    else:
        return render_template("workflows.html", data=workflows)

@app.route('/graph')
def graph():
    log_request()
    totable = "table" in request.args
    tordf = "rdf" in request.args

    uri = request.args.get("uri")
    if uri:
        g = get_graph(uri)

        logger.info("graph for", uri, g)

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

import pylogstash
log_stasher = pylogstash.LogStasher()

def log_request():
    request_summary = {'origin': 'odatests',
                 'url': url_for(request.endpoint),
                 'request-data': {
                    'headers': dict(request.headers),
                    'host_url': request.host_url,
                    'host': request.host,
                    'args': dict(request.args),
                    'json-data': dict(request.json or {}),
                    'form-data': dict(request.form or {}),
                }}
                    

    try:
        request_summary['clientip']=request_summary['request-data']['headers']['X-Forwarded-For'].split(",")[0]
        logger.info("extracted client:", request_summary['clientip'] )
    except Exception as e:
        logger.info("unable to extract client")

    logger.info(request_summary)

    log_stasher.log(request_summary)

@app.route('/data')
def viewdata():
    log_request()

    return_json = 'json' in request.args

    uri = request.args.get("uri")
    if uri:
        data = get_data(uri)
        if return_json:
            return jsonify(data)
        else:
            return render_template('viewdata.html', 
                        tnow=time.time(),
                        **data, 
                    )

    if return_json:
        return jsonify(list_data())

    f = request.args.get("f", None)

    odakb.sparql.reset_stats_collection()
    d = list_data(f)

    current_goals = get_goals("unreached", wf=f)
    
    request_stats = [dict(
                spent_seconds=sum(rs['spent_seconds'] for rs in odakb.sparql.query_stats),
                query_size=sum(rs['query_size'] for rs in odakb.sparql.query_stats),
            )]
    
        
    timestamps = get_timestamps()

    odakb.sparql.query_stats = None

    if len(d)>0:
        domains = set(functools.reduce(lambda x,y:x+y, [R.get('workflow_domains', []) for R in d]))
    else:
        domains = []

    r = render_template('data.html', 
                domains=domains,
                data=d, 
                tnow=time.time(),
                timestamps=timestamps[-3:],
                request_stats=request_stats,
                timestamp_now=time.time(),
                current_goals=current_goals,
            )



    return r

@app.route('/')
def viewdash():
    log_request()
    r = render_template('dashboard.html')
    return r

@app.template_filter()
def uri(uri, showwith=None):
    suri = uri.replace("http://odahub.io/ontology#", "oda:")
    suri = suri.replace("http://ddahub.io/ontology/data#", "data:")

    if showwith is None:
        return '<a href="graph?uri={quri}">{suri}</a>'.format(quri=quote_plus(uri), suri=suri)
    else:
        return '''<a href="{showwith}?uri={quri}">{suri}</a>
                  <a href="graph?uri={quri}"><img class="button" src="static/img/rdf.svg"/></a>
               '''.format(quri=quote_plus(uri), suri=suri, showwith=showwith)

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

    logger.info("evaluate this", w)


    r = restore(w) 

    if r is not None:
        return 'restored', r
    else:
        if allow_run:
            r = { 'origin':"run", **odarun.run(w) }

            s = store(w, r)
        
            if nuri(s['goal_uri']) != nuri(goal_uri):
                logger.info("stored goal uri", s['goal_uri'])
                logger.info("requested goal uri", goal_uri)
                raise Exception("inconsistent storage")

            return 'ran', r
        else:
            return None



def store(w, d):
    uri = w2uri(w)
    goal_uri = w2uri(w, "goal")

    logger.info("storing", d)

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

    logger.info("created, to insert:", s)

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
        logger.info("not known: %s"%uri)
        return None

    except odakb.sparql.ManyAnswers:
        logger.info("ambigiously known: %s"%uri)
        return None

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                                           'favicon.png', mimetype='image/vnd.microsoft.icon')

def listen(args):
    app.run(port=5555,debug=True,host=args.host,threaded=True)
    

@click.group()
def cli():
    pass

@cli.command()
def list_timestamps():
    get_timestamps()

@cli.command("list-data")
def _list_data():
    list_data()

@cli.command("expire-data")
def _expire_data():
    for ts in get_timestamps(f=None):
        print(ts[0])
        if time.time()-ts[0]>3*24*3600:
            print("expiring")
            odakb.sparql.reason(f'?d oda:curryied_input_timestamp "{ts[1]}"', '?d oda:realm oda:expired')
            return

@cli.command("list-goals")
@click.option("-f", default="")
def _list_goals(f):
    d = []
    for g in design_goals(f):
        print("designed goal:", g)
        d.append(g)

    json.dump(d, open("designed-goals.json", "wt"), indent=4)

if __name__ == "__main__":
    cli()
