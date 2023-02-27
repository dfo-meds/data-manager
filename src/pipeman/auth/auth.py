import flask_login as fl
import flask
import zirconium as zr
from autoinject import injector
import typing as t
from functools import wraps
from pipeman.i18n import gettext
from pipeman.util import System
import datetime


def require_permission(perm_names: t.Union[t.AnyStr, t.Iterable]):
    if isinstance(perm_names, str):
        perm_names = [perm_names]

    def _decorator(func: t.Callable) -> t.Callable:
        @wraps(func)
        def _decorated(*args, **kwargs):
            if not fl.current_user.is_authenticated:
                return flask.current_app.login_manager.unauthorized()
            if not any(fl.current_user.has_permission(x) for x in perm_names):
                return flask.current_app.login_manager.unauthorized()
            return flask.current_app.ensure_sync(func)(*args, **kwargs)
        return _decorated
    return _decorator


class AuthenticatedUser(fl.UserMixin):

    cfg: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self, username, display_name, permissions, organization_ids, dataset_ids, **extras):
        self.permissions = permissions
        self.display = display_name
        self.username = username
        self.organizations = organization_ids
        self.datasets = dataset_ids
        self._extras = extras
        to = self.cfg.as_int(("pipeman", "session_expiry"), default=44640)
        self.session_timeout = datetime.datetime.now() + datetime.timedelta(minutes=to)

    def property(self, name):
        if name in self._extras:
            return self._extras[name]
        return None

    def session_time_left(self):
        return int((self.session_timeout - datetime.datetime.now()).total_seconds())

    def get_id(self):
        return self.username

    def has_permission(self, permission_name):
        if permission_name == "_is_anonymous":
            return False
        if permission_name == "_is_not_anonymous":
            return True
        if "superuser" in self.permissions:
            return True
        return permission_name in self.permissions

    def belongs_to(self, organization_id):
        return organization_id in self.organizations

    def works_on(self, dataset_id):
        return dataset_id in self.datasets


class AnonymousUser(fl.AnonymousUserMixin):

    def __init__(self):
        self.display = "N/A"
        self.organizations = []
        self.datasets = []

    def belongs_to(self, organization_id):
        return False

    def has_permission(self, permission_name):
        return permission_name == "_is_anonymous"

    def works_on(self, dataset_id):
        return False

    def property(self, key):
        return None


@injector.injectable
class AuthenticationManager:

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self.login_success_route = self.config.as_str(("pipeman", "authentication", "login_success"), default="home")
        self.logout_success_route = self.config.as_str(("pipeman", "authentication", "logout_success"), default="home")
        self.unauthorized_route = self.config.as_str(("pipeman", "authentication", "unauthorized"), default="home")

    def login_handler(self):
        raise NotImplementedError()

    def logout_handler(self):
        raise NotImplementedError()

    def load_user(self, username):
        raise NotImplementedError()

    def login_from_request(self, request):
        return None

    def anonymous_user(self):
        return AnonymousUser()

    def login_success(self):
        return flask.redirect(flask.url_for(self.login_success_route))

    def logout_success(self):
        return flask.redirect(flask.url_for(self.logout_success_route))

    def unauthorized_handler(self):
        if flask.request.path.startswith("/api"):
            return flask.abort(403)
        else:
            flask.flash(gettext("pipeman.auth.not_authorized"), "error")
            return flask.redirect(flask.url_for(self.unauthorized_route))
