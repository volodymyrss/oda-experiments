from flask import url_for

def test_status(client):
    r = client.get("/status")
    print(r, r.json)

def test_get(client):
    r = client.get(url_for("tests_get"))
    print(r, r.json)

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
    r = client.get(url_for("goals_get"))
    print(r, r.json)
    

def test_list_testresults(client):
    r = client.get(url_for("data"))
    print(r.json)

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
