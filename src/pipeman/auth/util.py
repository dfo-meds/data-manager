"""Utility functions for managing groups"""
from pipeman.db import Database
import pipeman.db.orm as orm
from pipeman.util import UserInputError
import logging
import json
from pipeman.i18n import MultiLanguageString
from autoinject import injector
import zirconium as zr
import pathlib
import yaml


def load_groups_from_yaml(yaml_file):
    group_files = [pathlib.Path(__file__).absolute().parent / "groups.yaml"]
    with open(yaml_file, "r", encoding="utf-8") as h:
        groups = yaml.safe_load(h) or {}
        for gname in groups:
            try:
                create_group(gname)
            except UserInputError:
                continue
            for pname in groups[gname]:
                try:
                    grant_permission(gname, pname)
                except UserInputError:
                    continue


@injector.inject
def groups_select(db: Database = None):
    """Retrieve a list of groups suitable for a select list."""
    with db as session:
        return [
            (group.id, MultiLanguageString(json.loads(group.display_names) if group.display_names else {"und": group.short_name}))
            for group in session.query(orm.Group)
        ]


@injector.inject
def create_group(group_name: str, db: Database = None):
    """Create a new group."""
    with db as session:
        g = session.query(orm.Group).filter_by(short_name=group_name).first()
        if g:
            raise UserInputError("pipeman.auth.group_already_exists", group_name)
        g = orm.Group(
            short_name=group_name,
            permissions=""
        )
        session.add(g)
        session.commit()
        logging.getLogger("pipeman.auth").out(f"Created group {group_name}")


@injector.inject
def grant_permission(group_name: str, perm_name: str, db: Database = None):
    """Grant a permission to a group."""
    with db as session:
        g = session.query(orm.Group).filter_by(short_name=group_name).first()
        if not g:
            raise UserInputError("pipeman.auth.group_does_not_exist", group_name)
        g.add_permission(perm_name)
        session.commit()
        logging.getLogger("pipeman.auth").out(f"Granted permission {perm_name} to {group_name}")


@injector.inject
def revoke_permission(group_name: str, perm_name: str, db: Database = None):
    """Revoke a permission from a group."""
    with db as session:
        g = session.query(orm.Group).filter_by(short_name=group_name).first()
        if not g:
            raise UserInputError("pipeman.auth.group_does_not_exist", group_name)
        g.remove_permission(perm_name)
        session.commit()
        logging.getLogger("pipeman.auth").out(f"Revoked permission {perm_name} from {group_name}")


@injector.inject
def clear_permissions(group_name: str, db: Database = None):
    """Revoke a permission from a group."""
    with db as session:
        g = session.query(orm.Group).filter_by(short_name=group_name).first()
        if not g:
            raise UserInputError("pipeman.auth.group_does_not_exist", group_name)
        g.clear_permissions()
        session.commit()
        logging.getLogger("pipeman.auth").out(f"Cleared all permissions from {group_name}")
