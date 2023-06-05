"""Tools for authentication management."""
import json

import flask_login as fl
import flask
import zirconium as zr
from autoinject import injector
import typing as t
from functools import wraps
import zrlog
import datetime
from urllib.parse import urlparse
import itsdangerous
from pipeman.util.flask import flasht
from pipeman.util import load_object
from pipeman.i18n import gettext
from pipeman.util.flask import PipemanFlaskForm, NoControlCharacters, flasht
from pipeman.util.setup import invalidate_session, RequestInfo
import wtforms as wtf
import wtforms.validators as wtfv
from pipeman.i18n import DelayedTranslationString, TranslationManager, LanguageDetector
from pipeman.util.errors import PipemanError
from pipeman.db import Database
import pipeman.db.orm as orm
import base64
import sqlalchemy as sa
from .secure import SecurityHelper
import binascii


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
        self.log = zrlog.get_logger("pipeman.auth")
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
            return False
        if flask.request.method == "HEAD":
            return True
        if (not self._check_get_refs) and flask.request.method == "GET":
            return True
        ref = flask.request.headers.get("Referer")
        org = flask.request.headers.get("Origin")
        if org is None:
            org = ref
        pieces = urlparse(org)
        if self._allowed_hosts and pieces.netloc not in self._allowed_hosts:
            self.log.warning(f"Request denied because of bad referrer [{pieces.netloc}]")
            return False
        return True

    def check_for_https(self):
        """Check for HTTPS."""
        if not flask.has_request_context():
            return False
        if not self._require_https:
            return True
        pieces = urlparse(flask.request.url)
        if not pieces.scheme == "https":
            self.log.warning(f"Request denied because of no HTTPS")
            return False
        return True

    def check_access(self, perm_names: t.Iterable, check_referrer: bool = None, check_https: bool = None):
        """Check all configured requirements to access the page."""
        if not self.require_permissions(perm_names):
            self.log.warning(f"Request denied because of missing privileges {','.join(perm_names)}")
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
    def __init__(self, user_id: int, username: str, display_name: str, permissions: list, organization_ids: list, dataset_ids: list, **extras):
        self.user_id = user_id
        self.permissions = permissions
        self.display = display_name
        self.username = username
        self.organizations = organization_ids
        self.datasets = dataset_ids
        self._extras = extras
        to = self.cfg.as_int(("pipeman", "session_expiry"), default=44640)
        self.session_timeout = datetime.datetime.now() + datetime.timedelta(minutes=to)
        self._has_superuser_access = "superuser" in permissions and self.cfg.as_bool(("pipeman", "superuser_enabled"), default=True)

    def property(self, name: str, default = None) -> t.Any:
        """Retrieve the value of an extra user property as set by the authentication system."""
        if name in self._extras:
            return self._extras[name]
        return default

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
        if self._has_superuser_access:
            return True
        if permission_name == "_is_not_anonymous":
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
        self.user_id = None
        self.organizations = []
        self.datasets = []

    def belongs_to(self, organization_id):
        return False

    def has_permission(self, permission_name):
        return permission_name == "_is_anonymous" or permission_name == "_is_anyone"

    def works_on(self, dataset_id):
        return False

    def property(self, key, default=None):
        return default


class LoginForm(PipemanFlaskForm):
    """Form for logging in."""

    username = wtf.StringField(
        DelayedTranslationString("pipeman.label.user.username"),
        validators=[
            wtfv.InputRequired(message=DelayedTranslationString("pipeman.error.required_field")),
            NoControlCharacters()
        ]
    )
    password = wtf.PasswordField(
        DelayedTranslationString("pipeman.label.user.password"),
        validators=[
            wtfv.InputRequired(message=DelayedTranslationString("pipeman.error.required_field"))
        ]
    )

    submit = wtf.SubmitField(DelayedTranslationString("pipeman.common.submit"))


class AuthenticationHandler:

    config: zr.ApplicationConfig = None
    sh: SecurityHelper = None

    @injector.construct
    def __init__(self, auth_manager, handler_name: str):
        self._auth_manager = auth_manager
        self._handler_name = handler_name
        self._log = zrlog.get_logger(handler_name)

    def link(self):
        return flask.url_for('auth.login_method', method=self._handler_name)

    def display_name(self):
        raise NotImplementedError()

    def login_page(self):
        raise NotImplementedError()

    def logout(self):
        pass

    def update_user(self, user: AuthenticatedUser):
        pass

    def attempt_login_from_request(self, request):
        return None

    def login_from_redirect(self):
        return flask.abort(404)


class FormAuthenticationHandler(AuthenticationHandler):

    def login_page(self):
        form = LoginForm()
        if form.validate_on_submit():
            username = self.attempt_login(form.username.data, form.password.data)
            if username:
                return self._auth_manager.login_user(form.username.data, self._handler_name)
            else:
                flasht("pipeman.auth.page.form_login.error", "error")
        return flask.render_template(
            "form.html",
            form=form,
            title=gettext("pipeman.auth.page.form_login.title")
        )

    def attempt_login(self, username, password) -> str:
        raise NotImplementedError()


class DatabaseAuthenticationHandler(FormAuthenticationHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._max_failed_logins = self.config.as_int(("pipeman", "auth_db", "max_failed_logins"), 5)
        self._max_failed_login_window = self.config.as_int(("pipeman", "auth_db", "failed_login_window_hours"), 24)
        self._lockout_time = self.config.as_int(("pipeman", "auth_db", "failed_login_lockout_time"), 24)

    def display_name(self):
        return gettext("pipeman.login.database")

    @injector.inject
    def attempt_login(self, username, password, from_api: bool = False, db: Database = None):
        with db as session:
            user = self._get_valid_user(username, from_api, session)
            if user is None:
                return None
            if user.phash is None:
                self._record_login_attempt(username, from_api, "no password set", False)
                return None
            if not self.sh.check_secret(password, user.salt, user.phash):
                self._record_login_attempt(username, from_api, "bad password")
                return None
            self._record_login_attempt(username, from_api)
            return username

    def attempt_login_from_request(self, request):
        auth_header = request.headers.get('Authorization', default=None)
        if not auth_header:
            return None
        if ' ' not in auth_header:
            self._record_login_attempt("", True, "invalid auth header", False, False)
            return None
        scheme, token = auth_header.split(' ', maxsplit=1)
        if scheme.lower() == 'basic':
            return self._basic_auth(token)
        elif scheme.lower() == 'bearer':
            return self._bearer_auth(token)
        else:
            self._record_login_attempt("", True, "invalid auth scheme", False, False)
        return None

    def _get_valid_user(self, username, from_api, session):
        user = session.query(orm.User).filter_by(username=username).first()
        if not user:
            self._record_login_attempt(username, from_api, "bad username", False)
            return None
        right_now = datetime.datetime.now()
        if user.locked_until and user.locked_until >= right_now:
            flasht("pipeman.auth.error.account_locked", "warning")
            self._record_login_attempt(username, from_api, "locked", False, False)
            return None
        if from_api and not user.allowed_api_access:
            self._record_login_attempt(username, from_api, "no api access allowed", False)
            return None
        return user

    def _record_login_attempt(self, username, from_api, error_message=None, is_lockable_error: bool = None, create_record: bool = True, session=None):
        if error_message:
            if is_lockable_error is None:
                is_lockable_error = True
            self._log.warning(f"invalid login attempt {username}, {'yes' if from_api else 'no'}, {error_message}")
        else:
            is_lockable_error = False
            self._log.out(f"successful login attempt {username}, {'yes' if from_api else 'no'}")
        if create_record:
            self._create_login_record(username, from_api, error_message, is_lockable_error, session=session)

    def _create_login_record(self, *args, session=None, **kwargs):
        if session is None:
            self._create_login_record_no_session(*args, **kwargs)
        else:
            self._create_login_record_with_session(*args, **kwargs, session=session)

    @injector.inject
    def _create_login_record_no_session(self, *args, db: Database = None, **kwargs):
        with db as session:
            self._create_login_record_with_session(*args, **kwargs, session=session)

    @injector.inject
    def _create_login_record_with_session(self, username, from_api, error_message, is_lockable_error, session, rinfo: RequestInfo = None):
        user = session.query(orm.User).filter_by(username=username).first()
        if not error_message:
            self._clear_login_records(username, session)
            self._update_user_login_properties(user, session)
        ulr = orm.UserLoginRecord(
            username=username or None,
            attempt_time=datetime.datetime.now(),
            was_since_last_clear=True,
            lockable=is_lockable_error,
            was_success=not error_message,
            error_message=error_message or None,
            from_api=from_api,
            remote_ip=rinfo.remote_ip()
        )
        session.add(ulr)
        session.commit()
        if error_message and user:
            self._check_for_suspicious_activity(user, session)

    def _check_for_suspicious_activity(self, user, session):
        if self._max_failed_logins > 0 and self._max_failed_login_window > 0 and self._lockout_time > 0:
            cap_dt = datetime.datetime.now() - datetime.timedelta(hours=self._max_failed_login_window)
            failures = session.query(orm.UserLoginRecord).filter_by(username=user.username, lockable=True, was_success=False, was_since_last_clear=True).filter(orm.UserLoginRecord.attempt_time >= cap_dt).count()
            if failures >= self._max_failed_logins:
                self._log.warning(f"User has too many recent logins, locking account {user.username}")
                user.locked_until = datetime.datetime.now() + datetime.timedelta(hours=self._lockout_time)
                session.commit()
                flasht("pipeman.auth.error.too_many_recent_logins", "error")

    def _clear_login_records(self, username, session):
        self._log.info(f"Clearing old logins for old {username}")
        st = (
            sa.update(orm.UserLoginRecord)
            .where(orm.UserLoginRecord.username == username)
            .where(orm.UserLoginRecord.was_since_last_clear == True)
            .values(was_since_last_clear=False)
        )
        session.execute(st)
        session.commit()

    def _basic_auth(self, auth_header):
        try:
            auth_decoded = base64.b64decode(auth_header).decode("utf-8")
            if ":" not in auth_decoded:
                self._record_login_attempt("", True, "invalid formatting for basic auth, missing :", False, False)
                return None
            pieces = auth_decoded.split(":", maxsplit=1)
            if not len(pieces) == 2:
                self._record_login_attempt("", True, "invalid formatting for basic auth", False, False)
            return self.attempt_login(pieces[0], pieces[1], True)
        except binascii.Error:
            self._record_login_attempt("", True, "invalid base64 encoding for basic auth", False, False)
        except UnicodeError:
            self._record_login_attempt("", True, "invalid utf-8 encoding for basic auth", False, False)
        return None

    @injector.inject
    def _bearer_auth(self, auth_header, db: Database = None):
        prefix, key, username = self.sh.parse_auth_header(auth_header)
        if prefix is None:
            self._record_login_attempt("", True, "invalid bearer auth format", False, False)
            return None
        with db as session:
            user = self._get_valid_user(username, True, session)
            if user is None:
                return None
            key = session.query(orm.APIKey).filter_by(user_id=user.id, prefix=prefix).first()
            if not key:
                self._record_login_attempt(username, True, "no such API key", session=session)
                return None
            if not key.is_active:
                self._record_login_attempt(username, True, "inactive API key", session=session)
                return None
            gate_date = datetime.datetime.now()
            error = "expired api key"
            if key.expiry > gate_date:
                error = "invalid api token"
                if self.sh.check_secret(auth_header, key.key_salt, key.key_hash):
                    self._record_login_attempt(username, True, session=session)
                    if self.sh.is_hash_outdated(auth_header, key.key_salt, key.key_hash):
                        key.key_hash = self.sh.hash_secret(auth_header, key.key_salt)
                        session.commit()
                    return username
            if key.old_expiry > gate_date:
                error = "invalid api token"
                if self.sh.check_secret(auth_header, key.old_key_salt, key.old_key_hash):
                    self._record_login_attempt(username, True, session=session)
                    if self.sh.is_hash_outdated(auth_header, key.old_key_salt, key.old_key_hash):
                        key.old_key_hash = self.sh.hash_secret(auth_header, key.old_key_salt)
                        session.commit()
                    return username
            self._record_login_attempt(username, True, error, session=session)
        return None

    def _update_user_login_properties(self, user, session):
        last_success = None
        last_error = None
        last_success_ip = None
        last_error_ip = None
        total_errors = 0
        for attempt in session.query(orm.UserLoginRecord).filter_by(username=user.username).order_by(orm.UserLoginRecord.attempt_time.desc()):
            if attempt.was_success and not attempt.was_since_last_clear:
                last_success = attempt.attempt_time
                last_success_ip = attempt.remote_ip
                break
            elif last_error is None:
                last_error = attempt.attempt_time
                last_error_ip = attempt.remote_ip
                total_errors = 1
            else:
                total_errors += 1
        props = json.loads(user.properties) if user.properties else {}
        props['last_success'] = last_success.strftime("%Y-%m-%d %H:%M:%S") if last_success else ""
        props['last_error'] = last_error.strftime("%Y-%m-%d %H:%M:%S") if last_error else ""
        props['last_success_ip'] = last_success_ip if last_success_ip else ""
        props['last_error_ip'] = last_error_ip if last_error_ip else ""
        props['total_errors'] = total_errors
        user.properties = json.dumps(props)
        session.commit()


@injector.injectable_global
class AuthenticationManager:

    config: zr.ApplicationConfig = None
    ld: LanguageDetector = None
    tm: TranslationManager = None

    @injector.construct
    def __init__(self):
        self._log = zrlog.get_logger("pipeman.auth")
        self._login_managers: dict[str, AuthenticationHandler] = {
            "default": DatabaseAuthenticationHandler(self, "default")
        }
        others = self.config.as_dict(("pipeman", "authentication", "handlers"), default={})
        for hname in others:
            self._login_managers[hname] = load_object(others[hname])(self, hname)
        self._login_redirect = self.config.as_str(("pipeman", "authentication", "login_success"), default="base.home")
        self._logout_redirect = self.config.as_str(("pipeman", "authentication", "logout_success"), default="base.home")
        self._login_required_redirect = self.config.as_str(("pipeman", "authentication", "login_required"), default="auth.login")
        self._forbidden_redirect = self.config.as_str(("pipeman", "authentication", "unauthorized"), default="base.home")
        self._csrf_redirect = self.config.as_str(("pipeman", "authentication", "referrer_failed"), default="base.splash")
        _secret_key = self.config.get(("pipeman", "authentication", "next_signing_key"), default=None)
        if _secret_key is None:
            _secret_key = self.config.get(("flask", "SECRET_KEY"), default=None)
        self._serializer = None
        if _secret_key:
            if len(_secret_key) < 8:
                self._log.warning(f"Insufficient length for secret key (recommend 8+): {len(_secret_key)}")
            self._serializer = itsdangerous.URLSafeTimedSerializer(_secret_key, "pipeman_auth")

    def anonymous_user(self):
        return AnonymousUser()

    def unauthorized(self, result=RequestSecurity.FORBIDDEN):
        """Handle unauthorized requests."""
        # API calls start with /api and should return 403 instead of an error page.
        if flask.request.path.startswith("/api"):
            return flask.abort(403)
        # Error for if the user is not authenticated
        elif not fl.current_user.is_authenticated:
            flasht("pipeman.auth.error.login_required", 'error')
            next_page = ""
            if self._serializer:
                next_page = self._serializer.dumps(flask.request.url)
            return flask.redirect(flask.url_for(self._login_required_redirect, next_url=next_page))
        # This is for referrer or CSRF failure mostly
        elif result == RequestSecurity.TO_SPLASH:
            next_page = ""
            if self._serializer:
                next_page = self._serializer.dumps(flask.request.url)
            return flask.redirect(flask.url_for(self._csrf_redirect, next_url=next_page))
        # Error for if the user is authenticated but doesn't have sufficient access
        else:
            flasht("pipeman.auth.error.not_authorized", "error")
            return flask.redirect(flask.url_for(self._forbidden_redirect))

    def login_page(self):
        if len(self._login_managers) > 1:
            return flask.render_template('login_select.html',
                                         options=self._login_managers,
                                         title=gettext('pipeman.auth.page.login_select.title'))
        else:
            return self.login_page_for_handler(list(self._login_managers.keys())[0])

    def redirect_for_login(self, url_for_redirect, callback_handler):
        self._log.info(f"Setting session variables for redirect")
        flask.session['_auth_handler'] = callback_handler
        flask.session["_lang"] = self.ld.detect_language(self.tm.supported_languages())
        if "next_url" in flask.request.args and self._serializer:
            flask.session["_next_url"] = flask.request.args["next_url"]
        flask.session.modified = True
        return flask.redirect(url_for_redirect, 302)

    def redirect_handler_url(self):
        url = flask.url_for("auth.login_by_redirect", _external=True)
        if '?' in url:
            return url[:url.find('?')]
        return url

    def login_from_redirect(self):
        if '_auth_handler' in flask.session:
            handler = flask.session['_auth_handler']
            if handler in self._login_managers:
                return self._login_managers[handler].login_from_redirect()
            self._log.error(f"Handler {handler} not found when returning from redirect")
        else:
            self._log.error(f"No handler specified when returning from redirect")
        return self.login_page()

    def login_page_for_handler(self, handler_name: str):
        if handler_name not in self._login_managers:
            return flask.abort(404)
        return self._login_managers[handler_name].login_page()

    def login_from_request(self, request):
        for h in self._login_managers:
            username = self._login_managers[h].attempt_login_from_request(request)
            if username is not None:
                return self.load_user(username)
        return None

    def login_user(self, username: str, auth_handler_name: str):
        try:
            user = self.load_user(username)
            invalidate_session()
            fl.login_user(user)
            flasht("pipeman.auth.page.login.success", "success")
        except PipemanError as ex:
            self._log.exception(f"Exception while constructing user object for {username}")
        flask.session['auth_handler'] = auth_handler_name
        return self.login_success()

    def login_success(self):
        if self._serializer:
            try:
                next_signed = None
                if "_next_url" in flask.session:
                    next_signed = flask.session["_next_url"]
                elif "next_url" in flask.request.args:
                    next_signed = flask.request.args.get("next_url")
                if next_signed:
                    next_page = self._serializer.loads(flask.request.args.get("next_url"), max_age=1800)
                    return flask.redirect(next_page)
            except itsdangerous.BadData:
                self.log.exception(f"Exception while unserializing next_url")
                # Don't redirect without a proper signature
        lang = None
        if 'lang' in flask.request.args:
            lang = flask.request.args['lang']
        elif '_lang' in flask.session:
            lang = flask.session['_lang']
        if lang is None or lang not in self.tm.supported_languages():
            lang = ""
        return flask.redirect(flask.url_for(self._login_redirect, lang=lang))

    def logout_page(self):
        auth_handler = flask.session.get('auth_handler')
        if auth_handler:
            self._login_managers[auth_handler].logout()
        #invalidate_session()
        fl.logout_user()
        flask.session.modified = True
        flasht("pipeman.auth.page.logout.success", "success")
        return self.logout_success()

    def logout_success(self):
        return flask.redirect(flask.url_for(self._logout_redirect))

    @injector.inject
    def load_user(self, username, db: Database = None) -> AuthenticatedUser:
        with db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                return None
            permissions = set()
            for group in user.groups:
                permissions.update(group.permissions.split(";"))
            organizations = [x.id for x in user.organizations]
            datasets = [x.id for x in user.datasets]
            props = json.loads(user.properties) if user.properties else {}
            auth_handler = flask.session.get('auth_handler')
            full_user = AuthenticatedUser(
                user.id,
                user.username,
                user.display,
                list(permissions),
                organizations,
                datasets,
                **props
            )
            if auth_handler:
                self._login_managers[auth_handler].update_user(full_user)
            return full_user


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

