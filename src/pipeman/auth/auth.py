"""Tools for authentication management."""
import flask_login as fl
import flask
import zirconium as zr
from autoinject import injector
import typing as t
from functools import wraps
from pipeman.i18n import gettext
import datetime


def require_permission(perm_names: t.Union[t.AnyStr, t.Iterable]):
    """Ensure the current user is logged in and has one of the given permissions before allowing the request."""
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
    """Represents an authenticated user."""

    cfg: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self, username: str, display_name: str, permissions: list, organization_ids: list, dataset_ids: list, **extras):
        self.permissions = permissions
        self.display = display_name
        self.username = username
        self.organizations = organization_ids
        self.datasets = dataset_ids
        self._extras = extras
        to = self.cfg.as_int(("pipeman", "session_expiry"), default=44640)
        self.session_timeout = datetime.datetime.now() + datetime.timedelta(minutes=to)

    def property(self, name: str) -> t.Any:
        """Retrieve the value of an extra user property as set by the authentication system."""
        if name in self._extras:
            return self._extras[name]
        return None

    def session_time_left(self) -> int:
        """Retrieve the approximate amount of time left in the user's session."""
        return int((self.session_timeout - datetime.datetime.now()).total_seconds())

    def get_id(self):
        return self.username

    def has_permission(self, permission_name: str):
        """Check if the user has the given permission."""
        if permission_name == "_is_anonymous":
            return False
        if permission_name == "_is_not_anonymous":
            return True
        if "superuser" in self.permissions:
            return True
        return permission_name in self.permissions

    def belongs_to(self, organization_id):
        """Check if the user is a member of the given organization."""
        return organization_id in self.organizations

    def works_on(self, dataset_id):
        """Check if a user works on a given dataset."""
        return dataset_id in self.datasets


class AnonymousUser(fl.AnonymousUserMixin):
    """Anonymous implementation of the AuthenticatedUser."""

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
    """This class is designed to provide authentication services to the application.

    This is a stub implementation designed to be overridden by a specific provider which must follow this template.
    """

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self.login_success_route = self.config.as_str(("pipeman", "authentication", "login_success"), default="home")
        self.logout_success_route = self.config.as_str(("pipeman", "authentication", "logout_success"), default="home")
        self.unauthorized_route = self.config.as_str(("pipeman", "authentication", "unauthorized"), default="home")
        self.not_logged_in_route = self.config.as_str(("pipeman", "authentication", "login_required"), default="auth.login")

    def login_handler(self):
        """Display the login form or redirect to a third-party authorization page."""
        raise NotImplementedError()

    def logout_handler(self):
        """Display the logout form or otherwise end the session."""
        raise NotImplementedError()

    def load_user(self, username: str):
        """Load the user given their username."""
        raise NotImplementedError()

    def login_from_request(self, request):
        """Load a user from the request (e.g. the Authentication header)."""
        return None

    def anonymous_user(self):
        """Create an anonymous user."""
        return AnonymousUser()

    def login_success(self):
        """Redirect the user after successful login."""
        return flask.redirect(flask.url_for(self.login_success_route))

    def logout_success(self):
        """Redirect the user after successful logout."""
        return flask.redirect(flask.url_for(self.logout_success_route))

    def unauthorized_handler(self):
        """Handle unauthorized requests."""
        # API calls start with /api and should return 403 instead of an error page.
        if flask.request.path.startswith("/api"):
            return flask.abort(403)
        # Error for if the user is not authenticated
        elif not fl.current_user.is_authenticated():
            flask.flash(gettext("pipeman.auth.login_required"), "error")
            return flask.redirect(flask.url_for(self.not_logged_in_route))
        # Error for if the user is authenticated but doesn't have sufficient access
        else:
            flask.flash(gettext("pipeman.auth.not_authorized"), "error")
            return flask.redirect(flask.url_for(self.unauthorized_route))
