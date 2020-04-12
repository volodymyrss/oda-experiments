from flask import url_for

def test_status(client):
    r = client.get("/status")
    print(r, r.json)

def test_get(client):
    r = client.get(url_for("tests_get"))
    print(r, r.json)

def test_post(client):
    r = client.post(url_for("tests_post"))

    assert r.status_code == 200

    print(r, r.json)
