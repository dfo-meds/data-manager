"""Tools for authentication management."""
import flask_login as fl
import flask
import zirconium as zr
from autoinject import injector
import typing as t
from functools import wraps
from pipeman.i18n import gettext
import datetime
from urllib.parse import urlparse
import itsdangerous
import logging


@injector.injectable_global
class RequestSecurity:
    """Global security handler for requests"""

    cfg: zr.ApplicationConfig = None

    FORBIDDEN = "forbid"
    TO_SPLASH = "splash"
    ALLOWED = "allowed"

    @injector.construct
    def __init__(self):
        self._allowed_hosts = self.cfg.get(("pipeman", "security", "allowed_hosts"), default=[])
        self._require_https = self.cfg.as_bool(("pipeman", "security", "require_https"), default=False)
        self._check_get_refs = self.cfg.as_bool(("pipeman", "security", "check_get_referrers"), default=False)
        print(self._check_get_refs)
        self._check_refs_default = self.cfg.as_bool(("pipeman", "security", "check_refs_default"), default=True)
        self._check_https_default = self.cfg.as_bool(("pipeman", "security", "check_https_default"), default=True)

    def is_authenticated(self) -> bool:
        """Check if the user is authenticated."""
        if flask.has_request_context():
            return fl.current_user.is_authenticated
        return False

    def require_permissions(self, perm_names: t.Union[t.AnyStr, t.Iterable]) -> bool:
        """Check if the user has at least one of the given permissions."""
        if flask.has_request_context():
            cu = fl.current_user
            return any(cu.has_permission(x) for x in perm_names)
        return False

    def check_referrer(self):
        """Check that the referer is good."""
        if not flask.has_request_context():
            print("no request context")
            return False
        if flask.request.method == "HEAD":
            print("is head")
            return True
        if (not self._check_get_refs) and flask.request.method == "GET":
            print("is get")
            return True
        ref = flask.request.headers.get("Referer")
        org = flask.request.headers.get("Origin")
        if org is None:
            org = ref
        pieces = urlparse(org)
        if self._allowed_hosts and pieces.netloc not in self._allowed_hosts:
            return False
        return True

    def check_for_https(self):
        """Check for HTTPS."""
        if not flask.has_request_context():
            return False
        if not self._require_https:
            return True
        pieces = urlparse(flask.request.url)
        return pieces.scheme == "https"

    def check_access(self, perm_names: t.Iterable, check_referrer: bool = None, check_https: bool = None):
        """Check all configured requirements to access the page."""
        if not self.require_permissions(perm_names):
            return RequestSecurity.FORBIDDEN
        if check_referrer is None:
            check_referrer = self._check_refs_default
        if check_referrer and not self.check_referrer():
            return RequestSecurity.TO_SPLASH
        if check_https is None:
            check_https = self._check_https_default
        if check_https and not self.check_for_https():
            return RequestSecurity.TO_SPLASH
        return RequestSecurity.ALLOWED


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
        if permission_name == "_is_anyone":
            return True
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
        return permission_name == "_is_anonymous" or permission_name == "_is_anyone"

    def works_on(self, dataset_id):
        return False

    def property(self, key):
        return None


@injector.injectable_global
class AuthenticationManager:
    """This class is designed to provide authentication services to the application.

    This is a stub implementation designed to be overridden by a specific provider which must follow this template.
    """

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self.log = logging.getLogger("pipeman.auth")
        self.login_success_route = self.config.as_str(("pipeman", "authentication", "login_success"), default="base.home")
        self.logout_success_route = self.config.as_str(("pipeman", "authentication", "logout_success"), default="base.home")
        self.unauthorized_route = self.config.as_str(("pipeman", "authentication", "unauthorized"), default="base.home")
        self.not_logged_in_route = self.config.as_str(("pipeman", "authentication", "login_required"), default="auth.login")
        self.splash_route = self.config.as_str(("pipeman", "authentication", "splash_page"), default="base.splash")
        self.show_login_req = self.config.as_bool(("pipeman", "authentication", "show_login_required_message"), default=True)
        self.show_unauth = self.config.as_bool(("pipeman", "authentication", "show_unauthorized_required_message"), default=True)
        _secret_key = self.config.get(("pipeman", "authentication", "next_signing_key"), default=None)
        if _secret_key is None:
            _secret_key = self.config.get(("flask", "SECRET_KEY"), default=None)
        self._serializer = None
        if _secret_key:
            if len(_secret_key) < 20:
                self.log.warning(f"Insufficient length for secret key (recommend 20): {len(_secret_key)}")
            self._serializer = itsdangerous.URLSafeTimedSerializer(_secret_key, "pipeman_auth")

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
        if self._serializer:
            try:
                next_signed = flask.request.args.get("next_url", default=None)
                if next_signed:
                    next_page = self._serializer.loads(flask.request.args.get("next_url"), max_age=1800)
                    return flask.redirect(next_page)
            except itsdangerous.BadData as ex:
                self.log.warning(f"Exception while unserializing next_url: {str(ex)}")
                # Don't redirect without proper signatures
                pass
        return flask.redirect(flask.url_for(self.login_success_route))

    def logout_success(self):
        """Redirect the user after successful logout."""
        return flask.redirect(flask.url_for(self.logout_success_route))

    def unauthorized_handler(self, result=RequestSecurity.FORBIDDEN):
        """Handle unauthorized requests."""
        # API calls start with /api and should return 403 instead of an error page.
        if flask.request.path.startswith("/api"):
            return flask.abort(403)
        # Error for if the user is not authenticated
        elif not fl.current_user.is_authenticated:
            if self.show_login_req:
                flask.flash(gettext("pipeman.auth.login_required"), "error")
            next_page = ""
            if self._serializer:
                next_page = self._serializer.dumps(flask.request.url)
            return flask.redirect(flask.url_for(self.not_logged_in_route, next_url=next_page))
        # This is for referrer or CSRF failure mostly
        elif result == RequestSecurity.TO_SPLASH:
            return flask.redirect(flask.url_for(self.splash_route))
        # Error for if the user is authenticated but doesn't have sufficient access
        else:
            if self.show_unauth:
                flask.flash(str(gettext("pipeman.auth.not_authorized")), "error")
            return flask.redirect(flask.url_for(self.unauthorized_route))


def require_permission(perm_names: t.Union[t.AnyStr, t.Iterable], **perm_args):
    """Ensure the current user is logged in and has one of the given permissions before allowing the request."""
    if isinstance(perm_names, str):
        perm_names = [perm_names]

    def _decorator(func: t.Callable) -> t.Callable:
        @wraps(func)
        @injector.inject
        def _decorated(*args, rs: RequestSecurity = None, auth_man: AuthenticationManager = None, **kwargs):
            result = rs.check_access(perm_names, **perm_args)
            if result == RequestSecurity.ALLOWED:
                return flask.current_app.ensure_sync(func)(*args, **kwargs)
            else:
                return auth_man.unauthorized_handler(result)
        return _decorated

    return _decorator

