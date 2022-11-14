from pipeman.plugins.auth_form.controller import FormAuthenticationManager
from pipeman.auth.auth import AuthenticatedUser, hash_password
from pipeman.db.db import Database
from autoinject import injector
import pipeman.db.orm as orm
import secrets


class DatabaseEntityAuthenticationManager(FormAuthenticationManager):

    db: Database = None

    @injector.construct
    def __init__(self, form_template_name):
        super().__init__(form_template_name)

    def load_user(self, username):
        with self.db as session:
            user = session.query(orm.User).find_by(username=username)
            if user:
                return self._build_user(user)
        return None

    def find_user(self, username, password):
        with self.db as session:
            user = session.query(orm.User).find_by(username=username)
            if not user:
                return None
            pw_hash = hash_password(password, user.salt)
            if not secrets.compare_digest(pw_hash, user.pw_hash):
                return None
            return self._build_user(user)

    def _build_user(self, user):
        permissions = set()
        for group in user.groups:
            permissions.update(group.permissions.split(";"))
        return AuthenticatedUser(user.username, user.display, permissions)
