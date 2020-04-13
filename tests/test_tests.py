from flask import url_for

def test_status(client):
    r = client.get("/status")
    print(r, r.json)

def test_get(client):
    r = client.get(url_for("tests_get"))
    print(r, r.json)

def test_post(client):
    #from odatestsapp import capp

    #for rule in app.url_map.iter_rules():
    #    print("rule", rule, rule.endpoint, rule.methods)

    r = client.post(url_for("_default_auth_request_handler"))
    assert r.status_code == 200

    r = client.post(url_for("tests_post"))

    assert r.status_code == 200

    print(r, r.json)
