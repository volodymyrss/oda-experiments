from flask import url_for
import pytest

def test_status(client):
    r = client.get("/status")
    print(r, r.json)

def test_get(client):
    url = url_for("tests_get")

    print("url:", url)

    r = client.get(url)
    print(r, r.json)

def test_get_f(client):
    r = client.get(url_for("tests_get", f="?workflow oda:domain oda:common"))
    print(r, r.json)
    assert len(r.json)>0

def test_post(client):
    pass
    #from odatestsapp import capp

    #for rule in app.url_map.iter_rules():
    #    print("rule", rule, rule.endpoint, rule.methods)

 #   r = client.post(url_for("_default_auth_request_handler"))
 #   assert r.status_code == 200

 #   r = client.post(url_for("tests_post"))

 #   assert r.status_code == 200

  #  print(r, r.json)

def test_testgoals(client):
    from odakb.sparql import nuri

    import odaexperiments.app as odatestsapp
    odatestsapp.design_goals()

    r = client.get(url_for("goals_get"))
    print("all", r, len(r.json), r.json[:3],"...")
    r_all = r.json
    
    r = client.get(url_for("goals_get", f="unreached"))
    print("unreached", r, len(r.json), r.json[:3],"...")
    r_unr = r.json

    r = client.get(url_for("goals_get", f="reached"))
    print("reached", r, len(r.json), r.json[:3],"...")
    r_r = r.json

    g = client.get(url_for("offer_goal")).json
    u = nuri(g['goal_uri']).strip("<>")

    print("goal", u)
    print("in unr?", u in r_unr)
    print("in r?", u in r_r)
    print("in all?", u in r_all)

    assert u in r_unr
    assert u not in r_r

    ev = client.get(url_for("evaluate_one")).json
    u = nuri(g['goal_uri']).strip("<>")

    assert u in r_unr
    assert u not in r_r
    
    r = client.get(url_for("goals_get", f="unreached"))
    print("unreached", r, len(r.json), r.json[:3],"...")
    r_unr = r.json

    r = client.get(url_for("goals_get", f="reached"))
    print("reached", r, len(r.json), r.json[:3],"...")
    r_r = r.json
    
    assert u in r_r
    assert u not in r_unr

def test_design(client):
    import odaexperiments.app as odatestsapp
    goals = odatestsapp.design_goals()

    print(goals)

def test_view_testresults(client):
    r = client.get(url_for("viewdata"))
    print(r.json)

def test_put(client):
    r = client.put(url_for("tests_put", uri="oda:test-test", location="known"))
    print(r.json)

def test_get_testresults(client):
    pass

def test_evaluate_one(client):
    r = client.get(url_for("evaluate_one"))
    print(r, r.json)

def test_graph(client):
    r = client.get(url_for("graph", uri="http://odahub.io/ontology#test_lcpick_largebins"))
    print(r, r.json)

def test_graph_jsonld(client):
    r = client.get(url_for("graph", uri="http://odahub.io/ontology#test_lcpick_largebins", jsonld=True))
    print(r, r.json)

def test_wf_goal(client):
    g = client.get(url_for("offer_goal")).json

    g_pf = client.get(url_for("offer_goal", f="?w oda:callType oda:python_function")).json
    

    g_nb = client.get(url_for("offer_goal", f="?w oda:callType oda:jupyter_notebook")).json
    
    print()
    print("regular goal:", g)
    print("pf goal:", g_pf)
    print("nb goal:", g_nb)

def test_badrequest(client):
    r = client.get(url_for("offer_goal", f="oda:callType oda:jupyter_notebook"))

    assert r.status_code == 400

    print(r)

@pytest.mark.skip()
def test_unexpected(client):
    r = client.get(url_for("testerror"))

    assert r.status_code == 500

    print(r)


def test_run(client):
    import odaexperiments.run as odarun

    r = odarun.run(
        dict(
            base = dict(
                call_type="http://odahub.io/ontology#python_function",
                call_context="http://odahub.io/ontology#python3",
                location="https://raw.githubusercontent.com/volodymyrss/oda_test_kit/a86f682292e6233247bb299e5b4b5155faeaf214/odaplatform.py::platform_endpoint"                
            ),
            inputs=dict(
                cdciplatform="production"
            )
        )
    )

    assert r['result']['func_return'] == 'https://www.astro.unige.ch/mmoda'

def test_run_test_func():
    import odaexperiments.run as odarun
    f = odarun.test_func("odaplatform", "platform_endpoint")
    assert f(cdciplatform="production") == 'https://www.astro.unige.ch/mmoda'

