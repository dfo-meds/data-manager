from pipeman.builtins.auth_form.controller import FormAuthenticationManager
from pipeman.auth import AuthenticatedUser, SecurityHelper
from pipeman.db.db import Database
from autoinject import injector
import pipeman.db.orm as orm
from pipeman.util.flask import ConfirmationForm, paginate_query, ActionList, get_real_remote_ip, Select2Widget
from pipeman.i18n import gettext, DelayedTranslationString
import flask
import flask_login
from flask_wtf import FlaskForm
import wtforms as wtf
import wtforms.validators as wtfv
from pipeman.util.errors import UserInputError
from pipeman.auth.util import groups_select
from pipeman.org import OrganizationController
import base64
import datetime
import logging
import binascii
import sqlalchemy as sa
import zirconium as zr
import json


@injector.injectable
class DatabaseUserController:

    db: Database = None
    sh: SecurityHelper = None

    @injector.construct
    def __init__(self):
        pass

    def set_api_access(self, username, is_enabled: bool):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                raise ValueError("No such user")
            user.allowed_api_access = is_enabled
            session.commit()

    def create_api_key(self, username, display, expiry_days):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                raise ValueError("No such user")
            prefix = self.sh.generate_secret(32)
            raw_key = self.sh.generate_secret(64)
            key_salt = self.sh.generate_salt()
            auth_header = self.sh.build_auth_header(user.username, prefix, raw_key)
            key_hash = self.sh.hash_password(auth_header, key_salt)
            key = orm.APIKey(
                user_id=user.id,
                display=display,
                prefix=prefix,
                key_hash=key_hash,
                key_salt=key_salt,
                expiry=datetime.datetime.now() + datetime.timedelta(days=expiry_days),
                is_active=True,
                old_key_hash=None,
                old_key_salt=None,
                old_expiry=None
            )
            session.add(key)
            session.commit()
            print("API Key created. Please record these details as they will not be available again. Store them in a secure location.")
            print(f"Username: {username}")
            print(f"Prefix: {prefix}")
            print(f"Authorization: Bearer {auth_header}")
            print(f"Expiry: {key.expiry.strftime('%Y-%m-%d %H:%M:%S')}")
            print("To rotate the key, use rotate-api-key [USERNAME] [PREFIX].")

    def rotate_api_key(self, username, prefix, expiry_days, leave_old_active_days):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                raise ValueError("No such user")
            key = session.query(orm.APIKey).filter_by(user_id=user.id, prefix=prefix).first()
            if not key:
                raise ValueError("No such API key")
            raw_key = self.sh.generate_secret(64)
            key_salt = self.sh.generate_salt()
            auth_header = self.sh.build_auth_header(user.username, prefix, raw_key)
            key_hash = self.sh.hash_password(auth_header, key_salt)
            if leave_old_active_days > 0:
                key.old_key_hash = key.key_hash
                key.old_key_salt = key.key_salt
                key.old_expiry = datetime.datetime.now() + datetime.timedelta(days=leave_old_active_days)
            else:
                key.old_key_hash = None
                key.old_key_salt = None
                key.old_expiry = None
            key.key_salt = key_salt
            key.key_hash = key_hash
            key.expiry = datetime.datetime.now() + datetime.timedelta(days=expiry_days)
            session.commit()
            print(
                "API Key rotated. Please record these details as they will not be available again. Store them in a secure location.")
            print(f"Username: {username}")
            print(f"Prefix: {prefix}")
            print(f"Authorization: Bearer {auth_header}")
            print(f"Expiry: {key.expiry.strftime('%Y-%m-%d %H:%M:%S')}")
            if leave_old_active_days > 0:
                print(f"Old Key Expiry: {key.old_expiry.strftime('%Y-%m-%d %H:%M:%S')}")
            print("To rotate the key, use rotate-api-key [USERNAME] [PREFIX].")

    def view_myself_page(self):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=flask_login.current_user.get_id()).first()
            return flask.render_template("me.html", user=user)

    def edit_myself_form(self):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=flask_login.current_user.get_id()).first()
            form = EditMyselfForm(user=user)
            if form.validate_on_submit():
                user.display = form.display.data
                session.commit()
                return flask.redirect(flask.url_for("users.view_myself"))
            return flask.render_template("form.html", form=form, title=gettext("auth_db.edit_myself.title"))

    def change_password_form(self):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=flask_login.current_user.get_id()).first()
            form = ChangePasswordForm()
            if form.validate_on_submit():
                try:
                    self._set_password(user, form.password.data)
                    return flask.redirect(flask.url_for("users.view_myself"))
                except UserInputError as ex:
                    flask.flash(str(ex), "error")
            return flask.render_template("form.html", form=form, title=gettext("auth_db.change_password.title"))

    def list_users_page(self):
        with self.db as session:
            query = session.query(orm.User)
            query, page_args = paginate_query(query)
            create_link = ""
            if flask_login.current_user.has_permission("auth_db.create_users"):
                create_link = flask.url_for("users.create_user")
            return flask.render_template(
                "list_users.html",
                users=self._user_iterator(query),
                create_link=create_link,
                title=gettext("auth_db.user_list.title"),
                **page_args
            )

    def _build_action_list(self, user, short_mode: bool = True):
        actions = ActionList()
        kwargs = {'username': user.username}
        if short_mode:
            actions.add_action('pipeman.general.view', 'users.view_user', **kwargs)
        if flask_login.current_user.has_permission("auth_db.edit_users"):
            actions.add_action('pipeman.general.edit', 'users.edit_user', **kwargs)
        if flask_login.current_user.has_permission("auth_db.reset_passwords"):
            actions.add_action('auth_db.reset_password', 'users.reset_password', **kwargs)
        return actions

    def _user_iterator(self, query):
        for user in query:
            yield user, self._build_action_list(user, True)

    def create_user_form(self):
        form = CreateUserForm()
        if form.validate_on_submit():
            with self.db as session:
                u = session.query(orm.User.id).filter_by(username=form.username.data).first()
                ue = session.query(orm.User.id).filter_by(email=form.email.data).first()
                if u:
                    flask.flash(gettext("auth_db.create_user.error_already_exists"), "error")
                elif ue:
                    flask.flash(gettext("auth_db.create_user.error_email_exists"), "error")
                else:
                    pw = self.sh.random_password()
                    user = self._create_user(
                        form.username.data,
                        form.display.data,
                        form.email.data,
                        pw, session, True
                    )
                    for group_id in form.groups.data:
                        self._assign_to_group(user.id, group_id, session)
                    for org_id in form.organizations.data:
                        self._assign_to_org(user.id, org_id, session)
                    session.commit()
                    flask.flash(gettext("auth_db.create_user.success") + f" {pw}", "success")
                    return flask.redirect(flask.url_for("users.view_user", username=user.username))
        return flask.render_template("form.html", form=form, title=gettext("auth_db.user_create.title"))

    def create_user_cli(self, username, email, display, password):
        skip_check = False
        if password is None:
            password = self.sh.random_password()
            print(f"Randomly generated password: {password}")
            skip_check = True
        with self.db as session:
            u = session.query(orm.User.id).filter_by(username=username).first()
            if u:
                raise UserInputError("auth_db.cli.user_already_exists")
            self._create_user(username, display, email, password, session, skip_check)
            session.commit()

    def assign_to_org_cli(self, org_name, username):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                raise UserInputError("pipeman.plugins.auth_db.username_does_not_exist")
            org = session.query(orm.Organization).filter_by(short_name=org_name).first()
            if not org:
                raise UserInputError("pipeman.auth.org_does_not_exist")
            self._assign_to_org(user.id, org.id, session)
            session.commit()

    def remove_from_org_cli(self, org_name, username):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                raise UserInputError("pipeman.plugins.auth_db.username_does_not_exist")
            org = session.query(orm.Organization).filter_by(short_name=org_name).first()
            if not org:
                raise UserInputError("pipeman.auth.org_does_not_exist")
            self._remove_from_org(user.id, org.id, session)
            session.commit()

    def _assign_to_org(self, user_id, org_id, session):
        st = orm.user_organization.select().where(orm.user_organization.c.user_id == user_id).where(
            orm.user_organization.c.organization_id == org_id)
        res = session.execute(st).first()
        if not res:
            q = orm.user_organization.insert({
                "organization_id": org_id,
                "user_id": user_id
            })
            session.execute(q)

    def _remove_from_org(self, user_id, org_id, session):
        st = orm.user_organization.delete().where(orm.user_organization.c.user_id == user_id).where(
            orm.user_organization.c.organization_id == org_id)
        session.execute(st)

    def assign_to_group_cli(self, group_name, username):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                raise UserInputError("pipeman.plugins.auth_db.username_does_not_exist")
            group = session.query(orm.Group).filter_by(short_name=group_name).first()
            if not group:
                raise UserInputError("pipeman.auth.group_does_not_exist")
            self._assign_to_group(user.id, group.id, session)
            session.commit()

    def remove_from_group_cli(self, group_name, username):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                raise UserInputError("pipeman.plugins.auth_db.username_does_not_exist")
            group = session.query(orm.Group).filter_by(short_name=group_name).first()
            if not group:
                raise UserInputError("pipeman.auth.group_does_not_exist")
            self._remove_from_group(user.id, group.id, session)
            session.commit()

    def _assign_to_group(self, user_id, group_id, session):
        st = orm.user_group.select().where(orm.user_group.c.user_id == user_id).where(orm.user_group.c.group_id == group_id)
        res = session.execute(st).first()
        if not res:
            q = orm.user_group.insert({
                "group_id": group_id,
                "user_id": user_id
            })
            session.execute(q)

    def _remove_from_group(self, user_id, group_id, session):
        st = orm.user_group.delete().where(orm.user_group.c.user_id == user_id).where(orm.user_group.c.group_id == group_id)
        session.execute(st)

    def _create_user(self, username, display_name, email, password, session, skip_check=False):
        user = orm.User(
            username=username,
            display=display_name,
            email=email,
        )
        self._set_password(user, password, skip_check)
        session.add(user)
        return user

    def view_user_page(self, username):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                return flask.abort(404)
            return flask.render_template("user.html", user=user, title=user.username, actions=self._build_action_list(user, False))

    def edit_user_form(self, username):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                return flask.abort(404)
            form = EditUserForm(user=user)
            if form.validate_on_submit():
                ue = session.query(orm.User.id).filter_by(email=form.email.data).first()
                if ue and not user.id == ue.id:
                    flask.flash(gettext("auth_db.create_user.error_email_exists"), "error")
                else:
                    user.email = form.email.data
                    user.display = form.display.data
                    in_groups = form.groups.data
                    for group_id, _ in form.group_list:
                        if group_id in in_groups:
                            self._assign_to_group(user.id, group_id, session)
                        else:
                            self._remove_from_group(user.id, group_id, session)
                    in_orgs = form.organizations.data
                    for org_id, _ in form.org_list:
                        if org_id in in_orgs:
                            self._assign_to_org(user.id, org_id, session)
                        else:
                            self._remove_from_org(user.id, org_id, session)
                    session.commit()
                    flask.flash(gettext("auth_db.edit_user.success"), "success")
                    return flask.redirect(flask.url_for("users.view_user", username=user.username))
            return flask.render_template(
                "form.html",
                form=form,
                title=gettext("auth_db.user_edit.title")
            )

    def reset_password_form(self, username):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                return flask.abort(404)
            form = ConfirmationForm()
            if form.validate_on_submit():
                new_password = self._reset_password(user)
                session.commit()
                flask.flash(gettext("auth_db.reset_password.success") + f" {new_password}", "success")
                return flask.redirect(flask.url_for("users.view_user", username=username))
            return flask.render_template("form.html", form=form, title=gettext("auth_db.user_reset_password.title"), instructions=gettext("auth_db.reset_password.instructions"))

    def set_password_cli(self, username, password):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                raise UserInputError("auth_db.username_does_not_exist")
            self._set_password(user, password)
            session.commit()

    def _reset_password(self, user):
        password = self.sh.random_password()
        self._set_password(user, password, True)
        return password

    def _set_password(self, user, password, skip_check=False):
        if not skip_check:
            self.sh.check_password_strength(password)
        user.salt = self.sh.generate_salt()
        user.phash = self.sh.hash_password(password, user.salt)

    def unlock_user_account(self, username):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if user:
                user.locked_until = None
            st = sa.update(orm.UserLoginRecord).where(orm.UserLoginRecord.username == username).where(orm.UserLoginRecord.was_since_last_clear == True).values(was_since_last_clear=False)
            session.execute(st)
            session.commit()


class CreateUserForm(FlaskForm):

    oc: OrganizationController = None

    username = wtf.StringField(
        DelayedTranslationString("auth_db.username"),
        validators=[
            wtfv.InputRequired(
                message=DelayedTranslationString("pipeman.fields.required")
            )
        ]
    )

    display = wtf.StringField(
        DelayedTranslationString("auth_db.display_name"),
        validators=[
            wtfv.InputRequired(
                message=DelayedTranslationString("pipeman.fields.required")
            )
        ]
    )

    email = wtf.EmailField(
        DelayedTranslationString("auth_db.email"),
        validators=[
            wtfv.InputRequired(
                message=DelayedTranslationString("pipeman.fields.required")
            )
        ]
    )

    groups = wtf.SelectMultipleField(
        DelayedTranslationString("auth_db.groups"),
        coerce=int,
        widget=Select2Widget(allow_multiple=True, placeholder=DelayedTranslationString("pipeman.general.empty_select"))
    )
    organizations = wtf.SelectMultipleField(
        DelayedTranslationString("auth_db.organizations"),
        coerce=int,
        widget=Select2Widget(allow_multiple=True, placeholder=DelayedTranslationString("pipeman.general.empty_select"))
    )

    submit = wtf.SubmitField("pipeman.general.submit")

    @injector.construct
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_list = groups_select()
        self.groups.choices = self.group_list
        self.organizations.choices = self.oc.list_organizations()


class EditUserForm(FlaskForm):

    oc: OrganizationController = None

    display = wtf.StringField(
        DelayedTranslationString("auth_db.display_name"),
        validators=[
            wtfv.InputRequired(
                message=DelayedTranslationString("pipeman.fields.required")
            )
        ]
    )

    email = wtf.EmailField(
        DelayedTranslationString("auth_db.email"),
        validators=[
            wtfv.InputRequired(
                message=DelayedTranslationString("pipeman.fields.required")
            )
        ]
    )

    groups = wtf.SelectMultipleField(
        DelayedTranslationString("auth_db.groups"),
        coerce=int,
        widget=Select2Widget(allow_multiple=True, placeholder=DelayedTranslationString("pipeman.general.empty_select"))
    )
    organizations = wtf.SelectMultipleField(
        DelayedTranslationString("auth_db.organizations"),
        coerce=int,
        widget=Select2Widget(allow_multiple=True, placeholder=DelayedTranslationString("pipeman.general.empty_select"))
    )

    submit = wtf.SubmitField(DelayedTranslationString("pipeman.general.submit"))

    @injector.construct
    def __init__(self, *args, user=None, **kwargs):
        if user:
            kwargs["display"] = user.display
            kwargs["email"] = user.email
            kwargs["groups"] = [g.id for g in user.groups]
            kwargs["organizations"] = [o.id for o in user.organizations]
        super().__init__(*args, **kwargs)
        self.group_list = groups_select()
        self.groups.choices = self.group_list
        self.org_list = self.oc.list_organizations()
        self.organizations.choices = self.org_list


class EditMyselfForm(FlaskForm):

    display = wtf.StringField(
        DelayedTranslationString("auth_db.display_name"),
        validators=[
            wtfv.InputRequired(
                message=DelayedTranslationString("pipeman.fields.required")
            )
        ]
    )

    submit = wtf.SubmitField(DelayedTranslationString("pipeman.general.submit"))

    def __init__(self, *args, user=None, **kwargs):
        if user:
            kwargs['display'] = user.display
        super().__init__(*args, **kwargs)


class ChangePasswordForm(FlaskForm):

    password = wtf.PasswordField(
        DelayedTranslationString("auth_db.password"),
        validators=[
            wtfv.InputRequired(
                message=DelayedTranslationString("pipeman.fields.required")
            )
        ]
    )

    repeat_password = wtf.PasswordField(
        DelayedTranslationString("auth_db.repeat_password"),
        validators=[
            wtfv.EqualTo(
                "password",
                message=DelayedTranslationString("pipeman.fields.passwords_match")
            )
        ]
    )

    submit = wtf.SubmitField(DelayedTranslationString("pipeman.general.submit"))


class DatabaseEntityAuthenticationManager(FormAuthenticationManager):

    db: Database = None
    sh: SecurityHelper = None
    cfg: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self, form_template_name: str = "form.html"):
        super().__init__(form_template_name)
        self.log = logging.getLogger("pipeman.auth_db")
        self._max_failed_logins = self.cfg.as_int(("pipeman", "auth_db", "max_failed_logins"), 5)
        self._max_failed_login_window = self.cfg.as_int(("pipeman", "auth_db", "failed_login_window_hours"), 24)
        self._lockout_time = self.cfg.as_int(("pipeman", "auth_db", "failed_login_lockout_time"), 24)

    def load_user(self, username):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if user:
                return self._build_user(user, session)
        return None

    def _record_login_attempt(self, username, from_api, error_message=None, is_lockable_error: bool = None, create_record: bool = True):
        if error_message:
            if is_lockable_error is None:
                is_lockable_error = True
            self.log.warning(f"invalid login attempt {username}, {'yes' if from_api else 'no'}, {error_message}")
        else:
            is_lockable_error = False
            self.log.out(f"successful login attempt {username}, {'yes' if from_api else 'no'}")
        if create_record:
            self._create_login_record(username, from_api, error_message, is_lockable_error)

    def _create_login_record(self, username, from_api, error_message, is_lockable_error):
        with self.db as session:
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
                remote_ip=get_real_remote_ip()
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
                user.locked_until = datetime.datetime.now() + datetime.timedelta(hours=self._lockout_time)
                session.commit()
                flask.flash(gettext("auth_db.too_many_recent_logins"), "error")

    def _clear_login_records(self, username, session):
        st = (
            sa.update(orm.UserLoginRecord)
            .where(orm.UserLoginRecord.username == username)
            .where(orm.UserLoginRecord.was_since_last_clear == True)
            .values(was_since_last_clear=False)
        )
        session.execute(st)
        session.commit()

    def _get_valid_user(self, username, from_api, session):
        user = session.query(orm.User).filter_by(username=username).first()
        if not user:
            self._record_login_attempt(username, from_api, "bad username", False)
            return None
        right_now = datetime.datetime.now()
        if user.locked_until and user.locked_until >= right_now:
            flask.flash(gettext("auth_db.account_locked"), "warning")
            self._record_login_attempt(username, from_api, "locked", False, False)
            return None
        if from_api and not user.allowed_api_access:
            self._record_login_attempt(username, from_api, "no api access allowed", False)
            return None
        return user

    def attempt_login(self, username, password, from_api: bool = False):
        with self.db as session:
            user = self._get_valid_user(username, from_api, session)
            if user is None:
                return None
            if user.phash is None:
                self._record_login_attempt(username, from_api, "no password set", False)
                return None
            pw_hash = self.sh.hash_password(password, user.salt)
            if not self.sh.compare_digest(pw_hash, user.phash):
                self._record_login_attempt(username, from_api, "bad password")
                return None
            self._record_login_attempt(username, from_api)
            return self._build_user(user, session)

    def login_from_request(self, request):
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

    def _bearer_auth(self, auth_header):
        prefix, key, username = self.sh.parse_auth_header(auth_header)
        if prefix is None:
            self._record_login_attempt("", True, "invalid bearer auth format", False, False)
            return None
        with self.db as session:
            user = self._get_valid_user(username, True, session)
            if user is None:
                return None
            key = session.query(orm.APIKey).filter_by(user_id=user.id, prefix=prefix).first()
            if not key:
                self._record_login_attempt(username, True, "no such API key")
                return None
            if not key.is_active:
                self._record_login_attempt(username, True, "inactive API key")
                return None
            gate_date = datetime.datetime.now()
            error = "expired api key"
            if key.expiry > gate_date:
                error = "invalid api token"
                key_hash = self.sh.hash_password(auth_header, key.key_salt)
                if self.sh.compare_digest(key_hash, key.key_hash):
                    self._record_login_attempt(username, True)
                    return self._build_user(user, session)
            if key.old_expiry > gate_date:
                error = "invalid api token"
                key_hash = self.sh.hash_password(auth_header, key.old_key_salt)
                if self.sh.compare_digest(key_hash, key.old_key_hash):
                    self._record_login_attempt(username, True)
                    return self._build_user(user, session)
            self._record_login_attempt(username, True, error)
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
        props['last_success'] = last_success.strftime("%Y-%m-%d %H:%M:%S")
        props['last_error'] = last_error.strftime("%Y-%m-%d %H:%M:%S")
        props['last_success_ip'] = last_success_ip
        props['last_error_ip'] = last_error_ip
        props['total_errors'] = total_errors
        user.properties = json.dumps(props)
        session.commit()

    def _build_user(self, user, session):
        permissions = set()
        for group in user.groups:
            permissions.update(group.permissions.split(";"))
        organizations = [x.id for x in user.organizations]
        datasets = [x.id for x in user.datasets]
        props = json.loads(user.properties) if user.properties else {}
        props['last_success'] = datetime.datetime.strptime(props['last_success'], "%Y-%m-%d %H:%M:%S")
        props['last_error'] = datetime.datetime.strptime(props['last_error'], "%Y-%m-%d %H:%M:%S")
        return AuthenticatedUser(
            user.username,
            user.display,
            permissions,
            organizations,
            datasets,
            **props
        )
