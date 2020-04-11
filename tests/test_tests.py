from flask import url_for

def test_status(client):
    r = client.get("/status")
    print(r, r.json)

def test_list(client):
    r = client.get(url_for("tests_get"))
    print(r, r.json)

#def test_put(client):
#    r = client.put("/tests/")
#    print(r, r.json)
