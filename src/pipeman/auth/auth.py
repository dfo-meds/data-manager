import flask_login as fl
import flask
import zirconium as zr
from autoinject import injector
import hashlib
import typing as t
from functools import wraps


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

    def __init__(self, username, display_name, permissions):
        self.permissions = permissions
        self.display = display_name
        self.username = username

    def get_id(self):
        return self.username

    def has_permission(self, permission_name):
        return permission_name in self.permissions


class AnonymousUser(fl.AnonymousUserMixin):

    def __init__(self):
        self.display = "N/A"

    def has_permission(self, permission_name):
        return False


@injector.injectable
class AuthenticationManager:

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self.login_success_route = self.config.as_str(("pipeman", "authentication", "login_route"), default="/")
        self.logout_success_route = self.config.as_str(("pipeman", "authentication", "logout_route"), default="/")

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
        return flask.redirect(self.login_success_route)

    def logout_success(self):
        return flask.redirect(self.logout_success_route)
