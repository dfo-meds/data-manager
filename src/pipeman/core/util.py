from pipeman.db import Database
import pipeman.db.orm as orm
from pipeman.util import UserInputError
from pipeman.i18n import DelayedTranslationString, MultiLanguageString
import json
import logging
from autoinject import injector
import flask_login


@injector.inject
def create_organization(org_name, db: Database = None):
    with db as session:
        org = session.query(orm.Organization).filter_by(short_name=org_name).first()
        if org:
            raise UserInputError("pipeman.core.org_exists")
        org = orm.Organization(
            short_name=org_name
        )
        session.add(org)
        session.commit()
        logging.getLogger("pipeman.core").out(f"Organization {org_name} created")


@injector.inject
def organization_list(db: Database = None):
    with db as session:
        all_access = flask_login.current_user.has_permission("organization.manage_any")
        global_access = flask_login.current_user.has_permission("organization.manage_global")
        orgs = []
        if global_access:
            orgs.append((0, DelayedTranslationString("pipeman.organization.global")))
        for org in session.query(orm.Organization):
            if all_access or flask_login.current_user.belongs_to(org.id):
                orgs.append((org.id, MultiLanguageString(json.loads(org.display_names) if org.display_names else {'und': org.short_name})))
        return orgs


@injector.inject
def user_list(db: Database = None):
    with db as session:
        users = []
        for user in session.query(orm.User):
            users.append((user.id, user.display))
        return users