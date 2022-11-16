from pipeman.util import UserInputError
from pipeman.db import Database
from autoinject import injector
import logging
import pipeman.db.orm as orm
from pipeman.auth import SecurityHelper


@injector.inject
def create_user(username, display_name, email, password, db: Database = None, sh: SecurityHelper = None):
    with db as session:
        u = session.query(orm.User).filter_by(username=username).first()
        if u:
            raise UserInputError("pipeman.plugins.auth_db.username_exists")
        e = session.query(orm.User).filter_by(email=email).first()
        if e:
            raise UserInputError("pipeman.plugins.auth_db.email_exists")
        sh.check_password_strength(password)
        salt = sh.generate_salt()
        pw_hash = sh.hash_password(password, salt)
        u = orm.User(
            username=username,
            display=display_name,
            salt=salt,
            phash=pw_hash,
            email=email
        )
        session.add(u)
        session.commit()
        logging.getLogger("pipeman.plugins.auth_db").out(f"User {username} created")


@injector.inject
def assign_to_group(group_name, username, db: Database = None):
    with db as session:
        user = session.query(orm.User).filter_by(username=username).first()
        if not user:
            raise UserInputError("pipeman.plugins.auth_db.username_does_not_exist")
        group = session.query(orm.Group).filter_by(short_name=group_name).first()
        if not group:
            raise UserInputError("pipeman.auth.group_does_not_exist")
        st = orm.user_group.select().where(orm.user_group.c.user_id == user.id).where(orm.user_group.c.group_id == group.id)
        res = session.execute(st).first()
        if not res:
            q = orm.user_group.insert({
                "group_id": group.id,
                "user_id": user.id
            })
            session.execute(q)
            session.commit()
        logging.getLogger("pipeman.plugins.auth_db").out(f"User {username} assigned to group {group_name}")



@injector.inject
def remove_from_group(group_name, username, db: Database = None):
    with db as session:
        user = session.query(orm.User).filter_by(username=username).first()
        if not user:
            raise UserInputError("pipeman.plugins.auth_db.username_does_not_exist")
        group = session.query(orm.Group).filter_by(short_name=group_name).first()
        if not group:
            raise UserInputError("pipeman.auth.group_does_not_exist")
        st = orm.user_group.delete().where(orm.user_group.c.user_id == user.id).where(orm.user_group.c.group_id == group.id)
        session.execute(st)
        session.commit()
        logging.getLogger("pipeman.plugins.auth_db").out(f"User {username} removed from group {group_name}")
