from playhouse.db_url import connect
from playhouse.shortcuts import model_to_dict, dict_to_model

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


