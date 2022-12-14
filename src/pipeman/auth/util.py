from autoinject import injector
from pipeman.db import Database
import pipeman.db.orm as orm
from pipeman.util import UserInputError
import logging
import json
from pipeman.i18n import MultiLanguageString


@injector.inject
def groups_select(db: Database = None):
    with db as session:
        return [
            (group.id, MultiLanguageString(json.loads(group.display_names) if group.display_names else {"und": group.short_name}))
            for group in session.query(orm.Group)
        ]


@injector.inject
def create_group(group_name, db: Database = None):
    with db as session:
        g = session.query(orm.Group).filter_by(short_name=group_name).first()
        if g:
            raise UserInputError("pipeman.auth.group_exists", group_name)
        g = orm.Group(
            short_name=group_name,
            permissions=""
        )
        session.add(g)
        session.commit()
        logging.getLogger("pipeman.auth").out(f"Created group {group_name}")


@injector.inject
def grant_permission(group_name, perm_name, db: Database = None):
    with db as session:
        g = session.query(orm.Group).filter_by(short_name=group_name).first()
        if not g:
            raise UserInputError("pipeman.auth.group_does_not_exist", group_name)
        g.add_permission(perm_name)
        session.commit()
        logging.getLogger("pipeman.auth").out(f"Granted permission {perm_name} to {group_name}")


@injector.inject
def revoke_permission(group_name, perm_name, db: Database = None):
    with db as session:
        g = session.query(orm.Group).filter_by(short_name=group_name).first()
        if not g:
            raise UserInputError("pipeman.auth.group_does_not_exist", group_name)
        g.remove_permission(perm_name)
        session.commit()
        logging.getLogger("pipeman.auth").out(f"Revoked permission {perm_name} from {group_name}")
