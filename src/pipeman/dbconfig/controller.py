from pipeman.db import Database
from autoinject import injector
import pipeman.db.orm as orm
import json


@injector.injectable
class ValueController:

    db: Database = None

    @injector.construct
    def __init__(self):
        pass

    def get_value(self, key, default=None):
        with self.db as session:
            entry = session.query(orm.KeyValue).filter_by(key=key).first()
            if entry and entry.value:
                return json.loads(entry.value)
        return default

    def set_value(self, key, value):
        with self.db as session:
            entry = session.query(orm.KeyValue).filter_by(key=key).first()
            if entry:
                entry.value = json.dumps(value)
            else:
                entry = orm.KeyValue(key=key, value=json.dumps(value))
                session.add(entry)
            session.commit()



