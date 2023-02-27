from pipeman.util import UserInputError
from pipeman.db import Database
from autoinject import injector
import logging
import pipeman.db.orm as orm


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


@injector.inject
def assign_to_organization(organization_name, username, db: Database = None):
    with db as session:
        user = session.query(orm.User).filter_by(username=username).first()
        if not user:
            raise UserInputError("pipeman.plugins.auth_db.username_does_not_exist")
        org = session.query(orm.Organization).filter_by(short_name=organization_name).first()
        if not org:
            raise UserInputError("pipeman.core.org_not_found")
        st = orm.user_organization.select().where(orm.user_organization.c.user_id == user.id).where(orm.user_organization.c.organization_id == org.id)
        res = session.execute(st).first()
        if not res:
            q = orm.user_organization.insert({
                "organization_id": org.id,
                "user_id": user.id
            })
            session.execute(q)
            session.commit()
        logging.getLogger("pipeman.plugins.auth_db").out(f"User {username} assigned to organization {organization_name}")


@injector.inject
def remove_from_organization(organization_name, username, db: Database = None):
    with db as session:
        user = session.query(orm.User).filter_by(username=username).first()
        if not user:
            raise UserInputError("pipeman.plugins.auth_db.username_does_not_exist")
        org = session.query(orm.Organization).filter_by(short_name=organization_name).first()
        if not org:
            raise UserInputError("pipeman.core.org_not_found")
        st = orm.user_organization.delete().where(orm.user_organization.c.user_id == user.id).where(
            orm.user_organization.c.organization_id == org.id)
        session.execute(st)
        session.commit()
        logging.getLogger("pipeman.plugins.auth_db").out(f"User {username} removed from organization {organization_name}")
