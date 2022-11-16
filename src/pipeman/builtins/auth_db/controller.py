from pipeman.builtins.auth_form.controller import FormAuthenticationManager
from pipeman.auth import AuthenticatedUser, SecurityHelper
from pipeman.db.db import Database
from autoinject import injector
import pipeman.db.orm as orm


class DatabaseEntityAuthenticationManager(FormAuthenticationManager):

    db: Database = None
    sh: SecurityHelper = None

    @injector.construct
    def __init__(self, form_template_name: str = "form.html"):
        super().__init__(form_template_name)

    def load_user(self, username):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if user:
                return self._build_user(user)
        return None

    def find_user(self, username, password):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                return None
            if user.phash is None:
                return None
            pw_hash = self.sh.hash_password(password, user.salt)
            if not self.sh.compare_digest(pw_hash, user.phash):
                return None
            return self._build_user(user)

    def _build_user(self, user):
        permissions = set()
        for group in user.groups:
            permissions.update(group.permissions.split(";"))
        return AuthenticatedUser(user.username, user.display, permissions)
