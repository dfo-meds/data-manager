import flask_login as fl
import flask
import zirconium as zr
from autoinject import injector
import hashlib


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
