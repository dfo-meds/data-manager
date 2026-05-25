from pipeman.db import Database
import pipeman.db.orm as orm
from autoinject import injector


@injector.inject
def user_list(db: Database = None):
    with db as session:
        users = []
        for user in session.query(orm.User):
            users.append((user.id, user.display))
        return users
