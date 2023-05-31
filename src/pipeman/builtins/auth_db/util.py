from pipeman.util import UserInputError
from pipeman.db import Database
from autoinject import injector
import zrlog
import pipeman.db.orm as orm


@injector.inject
def remove_from_group(group_name, username, db: Database = None):
    with db as session:
        user = session.query(orm.User).filter_by(username=username).first()
        if not user:
            raise UserInputError("pipeman.auth_db.error.user_does_not_exist")
        group = session.query(orm.Group).filter_by(short_name=group_name).first()
        if not group:
            raise UserInputError("pipeman.auth.error.group_does_not_exist")
        st = orm.user_group.delete().where(orm.user_group.c.user_id == user.id).where(orm.user_group.c.group_id == group.id)
        session.execute(st)
        session.commit()
        zrlog.get_logger("pipeman.auth_db").notice(f"User {username} removed from group {group_name}")


@injector.inject
def assign_to_organization(organization_name, username, db: Database = None):
    with db as session:
        user = session.query(orm.User).filter_by(username=username).first()
        if not user:
            raise UserInputError("pipeman.auth_db.error.user_does_not_exist")
        org = session.query(orm.Organization).filter_by(short_name=organization_name).first()
        if not org:
            raise UserInputError("pipeman.org.error.org_does_not_exist")
        st = orm.user_organization.select().where(orm.user_organization.c.user_id == user.id).where(orm.user_organization.c.organization_id == org.id)
        res = session.execute(st).first()
        if not res:
            q = orm.user_organization.insert().values({
                "organization_id": org.id,
                "user_id": user.id
            })
            session.execute(q)
            session.commit()
        zrlog.get_logger("pipeman.auth_db").notice(f"User {username} assigned to organization {organization_name}")


@injector.inject
def remove_from_organization(organization_name, username, db: Database = None):
    with db as session:
        user = session.query(orm.User).filter_by(username=username).first()
        if not user:
            raise UserInputError("pipeman.auth_db.error.user_does_not_exist")
        org = session.query(orm.Organization).filter_by(short_name=organization_name).first()
        if not org:
            raise UserInputError("pipeman.org.error.org_does_not_exist")
        st = orm.user_organization.delete().where(orm.user_organization.c.user_id == user.id).where(
            orm.user_organization.c.organization_id == org.id)
        session.execute(st)
        session.commit()
        zrlog.get_logger("pipeman.auth_db").notice(f"User {username} removed from organization {organization_name}")
