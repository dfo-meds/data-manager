from pipeman.db import Database
import pipeman.db.orm as orm
from autoinject import injector
from pipeman.util import UserInputError
import pathlib
import zirconium as zr
import yaml


@injector.inject
def user_list(db: Database = None):
    with db as session:
        users = []
        for user in session.query(orm.User):
            users.append((user.id, user.display))
        return users


@injector.inject
def setup_core_groups(cfg: zr.ApplicationConfig = None):
    from pipeman.auth.util import create_group, grant_permission
    group_files = [pathlib.Path(__file__).absolute().parent / "groups.yaml"]
    group_files.extend(cfg.get(("pipeman", "group_files"), default=[]))
    for file in group_files:
        file = pathlib.Path(file)
        if file.exists():
            with open(file, "r", encoding="utf-8") as h:
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
