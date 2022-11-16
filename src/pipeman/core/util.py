from pipeman.db import Database
import pipeman.db.orm as orm
from pipeman.util import UserInputError
import logging
from autoinject import injector


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
