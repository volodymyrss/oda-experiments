from flask import Flask
from flask import render_template,make_response,request,jsonify

import peewee
import datetime
import yaml
import io


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

@app.route('/tests')
def tests_get(methods=["GET"]):
    tests=[]

    for r in odakb.sparql.select(query="""
                    ?test oda:belongsTo oda:basic_testkit; 
                          a oda:test;
                          a oda:workflow;
                          oda:callType ?call_type;
                          oda:location ?location
                    """)['results']['bindings']:


        print("test:", t)

        tests.append(t)

    return jsonify(tests)


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

@app.route('/', methods=["GET"])
def goals_get():
    tests=[]

    for r in odakb.sparql.select(query="""
                    ?test oda:belongsTo oda:basic_testkit; 
                          a oda:test;
                          a oda:workflow;
                          oda:callType ?call_type;
                          oda:location ?location;
                    """)['results']['bindings']:

        t = { k: v['value'] for k, v in r.items() }
        
        print("test:", t)

        t['expects'] = []

        for r in odakb.sparql.select(query="""
                        %s oda:expects ?expectation 
                        """%t['test'])['results']['bindings']:

            t['expects'].append()



        tests.append(t)

    return jsonify({})

@app.route('/goals', methods=["GET"])
def goals_get():
    tests=[]

    for r in odakb.sparql.select(query="""
                    ?test oda:belongsTo oda:basic_testkit; 
                          a oda:test;
                          a oda:workflow;
                          oda:callType ?call_type;
                          oda:location ?location
                    """)['results']['bindings']:

        t = { k: v['value'] for k, v in r.items() }

        print("test:", t)

        tests.append(t)

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
def list():
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

#from gunicorn.app.base import Application
#Application().run(app,port=5555,debug=True,host=args.host)

#       MyApplication().run()


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
