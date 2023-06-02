from pipeman.builtins.auth_form.controller import FormAuthenticationManager
from pipeman.auth import AuthenticatedUser, SecurityHelper
from pipeman.db.db import Database
from autoinject import injector
import pipeman.db.orm as orm
from pipeman.util.flask import ConfirmationForm, ActionList, Select2Widget, RequestInfo
from pipeman.i18n import gettext, DelayedTranslationString
import flask
import flask_login
import wtforms as wtf
import wtforms.validators as wtfv
from pipeman.util.errors import UserInputError
from pipeman.auth.util import groups_select
from pipeman.org import OrganizationController
import base64
import datetime
import zrlog
import binascii
import sqlalchemy as sa
import zirconium as zr
import json
from pipeman.util.flask import DataQuery, DataTable, DatabaseColumn, ActionListColumn, flasht, PipemanFlaskForm


@injector.injectable
class DatabaseUserController:

    db: Database = None
    sh: SecurityHelper = None

    @injector.construct
    def __init__(self):
        self.log = zrlog.get_logger("pipeman.auth_db")

    def set_api_access(self, username, is_enabled: bool):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                raise UserInputError("pipeman.auth_db.error.user_does_not_exist")
            user.allowed_api_access = is_enabled
            session.commit()
            self.log.notice(f"API access for {username} set to {is_enabled}")

    def create_api_key(self, username, display, expiry_days):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                raise UserInputError("pipeman.auth_db.error.user_does_not_exist")
            prefix = self.sh.generate_secret(32)
            raw_key = self.sh.generate_secret(64)
            key_salt = self.sh.generate_salt()
            auth_header = self.sh.build_auth_header(user.username, prefix, raw_key)
            key_hash = self.sh.hash_secret(auth_header, key_salt)
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
            self.log.notice(f"API key for {prefix}.{username} created")
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
                raise UserInputError("pipeman.auth_db.error.user_does_not_exist")
            key = session.query(orm.APIKey).filter_by(user_id=user.id, prefix=prefix).first()
            if not key:
                raise UserInputError("pipeman.auth_db.error.api_key_does_not_exist")
            raw_key = self.sh.generate_secret(64)
            key_salt = self.sh.generate_salt()
            auth_header = self.sh.build_auth_header(user.username, prefix, raw_key)
            key_hash = self.sh.hash_secret(auth_header, key_salt)
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
            self.log.notice(f"API key rotated for {prefix}.{username}; old key expires {key.old_expiry}")
            print("API Key rotated. Please record these details securely as they will not be available again.")
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
            return flask.render_template(
                "me.html", 
                user=user,
                title=gettext("pipeman.auth_db.page.view_myself.title", username=user.username)
            )

    def edit_myself_form(self):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=flask_login.current_user.get_id()).first()
            form = EditMyselfForm(user=user)
            if form.validate_on_submit():
                user.display = form.display.data
                session.commit()
                flasht("pipeman.auth_db.page.edit_myself.success", 'success')
                return flask.redirect(flask.url_for("users.view_myself"))
            return flask.render_template("form.html", form=form, title=gettext("pipeman.auth_db.page.edit_myself.title"))

    def change_password_form(self):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=flask_login.current_user.get_id()).first()
            form = ChangePasswordForm()
            if form.validate_on_submit():
                try:
                    self._set_password(user, form.password.data)
                    flasht("pipeman.auth_db.page.change_password.success", 'success')
                    return flask.redirect(flask.url_for("users.view_myself"))
                except UserInputError as ex:
                    flask.flash(str(ex), "error")
            return flask.render_template(
                "form.html", 
                form=form, 
                title=gettext("pipeman.auth_db.page.change_password.title"),
                instructions=gettext("pipeman.auth_db.page.change_password.instructions")
            )

    def list_users_page(self):
        links = []
        if flask_login.current_user.has_permission("auth_db.create"):
            links.append((
                flask.url_for("users.create_user"),
                gettext("pipeman.auth_db.page.create_user.link")
            ))
        return flask.render_template(
            "data_table.html",
            table=self._users_table(),
            side_links=links,
            title=gettext("pipeman.auth_db.page.list_users.title"),
        )

    def list_users_ajax(self):
        return self._users_table().ajax_response()

    def _users_table(self):
        dq = DataQuery(orm.User)
        dt = DataTable(
            table_id="user_list",
            base_query=dq,
            ajax_route=flask.url_for("users.list_users_ajax"),
            default_order=[("username", "asc")]
        )
        dt.add_column(DatabaseColumn("id", gettext("pipeman.label.user.id"), allow_order=True))
        dt.add_column(DatabaseColumn("username", gettext("pipeman.label.user.username"), allow_order=True, allow_search=True))
        dt.add_column(DatabaseColumn("display", gettext("pipeman.label.user.display_name"), allow_order=True, allow_search=True))
        dt.add_column(ActionListColumn(
            action_callback=self._build_action_list
        ))
        return dt

    def _build_action_list(self, user, short_mode: bool = True):
        actions = ActionList()
        kwargs = {'user_id': user.id}
        if short_mode:
            actions.add_action('pipeman.auth_db.page.view_user.link', 'users.view_user', **kwargs)
        if flask_login.current_user.has_permission("auth_db.edit"):
            actions.add_action('pipeman.auth_db.page.edit_user.link', 'users.edit_user', **kwargs)
        if flask_login.current_user.has_permission("auth_db.reset"):
            actions.add_action('pipeman.auth_db.page.reset_password.link', 'users.reset_password', **kwargs)
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
                    flasht("pipeman.auth_db.error.username_already_exists", "error")
                    self.log.warning(f"New user username conflicts with {u.id}")
                elif ue:
                    flasht("pipeman.auth_db.error.email_already_exists", "error")
                    self.log.warning(f"New user email conflicts with {ue.id}")
                else:
                    pw = self.sh.random_password()
                    user = self._create_user(
                        form.username.data,
                        form.display.data,
                        form.email.data,
                        pw, session, True
                    )
                    session.commit()
                    for group_id in form.groups.data:
                        self._assign_to_group(user.id, group_id, session)
                    for org_id in form.organizations.data:
                        self._assign_to_org(user.id, org_id, session)
                    session.commit()
                    flasht("pipeman.auth_db.page.create_user.success", "success", password=pw)
                    return flask.redirect(flask.url_for("users.view_user", user_id=user.id))
        return flask.render_template("form.html", form=form, title=gettext("pipeman.auth_db.page.create_user.title"))

    def create_user_cli(self, username, email, display, password):
        skip_check = False
        if password is None:
            password = self.sh.random_password()
            skip_check = True
        with self.db as session:
            u = session.query(orm.User.id).filter_by(username=username).first()
            if u:
                raise UserInputError("pipeman.auth_db.error.username_already_exists")
            ue = session.query(orm.User.id).filter_by(email=email).first()
            if ue:
                raise UserInputError("pipeman.auth_db.error.email_already_exists")
            self._create_user(username, display, email, password, session, skip_check)
            session.commit()

    def assign_to_org_cli(self, org_name, username):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                raise UserInputError("pipeman.auth_db.error.user_does_not_exist")
            org = session.query(orm.Organization).filter_by(short_name=org_name).first()
            if not org:
                raise UserInputError("pipeman.org.error.org_does_not_exist")
            self._assign_to_org(user.id, org.id, session)
            session.commit()

    def remove_from_org_cli(self, org_name, username):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                raise UserInputError("pipeman.auth_db.error.user_does_not_exist")
            org = session.query(orm.Organization).filter_by(short_name=org_name).first()
            if not org:
                raise UserInputError("pipeman.org.error.org_does_not_exist")
            self._remove_from_org(user.id, org.id, session)
            session.commit()

    def _assign_to_org(self, user_id, org_id, session):
        st = orm.user_organization.select().where(orm.user_organization.c.user_id == user_id).where(
            orm.user_organization.c.organization_id == org_id)
        res = session.execute(st).first()
        if not res:
            q = orm.user_organization.insert().values({
                "organization_id": org_id,
                "user_id": user_id
            })
            session.execute(q)
            self.log.notice(f"User {user_id} added to organization {org_id}")

    def _remove_from_org(self, user_id, org_id, session):
        st = orm.user_organization.delete().where(orm.user_organization.c.user_id == user_id).where(
            orm.user_organization.c.organization_id == org_id)
        session.execute(st)
        self.log.notice(f"User {user_id} removed from organization {org_id}")

    def assign_to_group_cli(self, group_name, username):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                raise UserInputError("pipeman.auth_db.error.user_does_not_exist")
            group = session.query(orm.Group).filter_by(short_name=group_name).first()
            if not group:
                raise UserInputError("pipeman.auth.error.group_does_not_exist")
            self._assign_to_group(user.id, group.id, session)
            session.commit()

    def remove_from_group_cli(self, group_name, username):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                raise UserInputError("pipeman.auth_db.error.user_does_not_exist")
            group = session.query(orm.Group).filter_by(short_name=group_name).first()
            if not group:
                raise UserInputError("pipeman.auth.error.group_does_not_exist")
            self._remove_from_group(user.id, group.id, session)
            session.commit()

    def _assign_to_group(self, user_id, group_id, session):
        st = orm.user_group.select().where(orm.user_group.c.user_id == user_id).where(orm.user_group.c.group_id == group_id)
        res = session.execute(st).first()
        if not res:
            q = orm.user_group.insert().values({
                "group_id": group_id,
                "user_id": user_id
            })
            session.execute(q)
            self.log.notice(f"User {user_id} added to group {group_id}")

    def _remove_from_group(self, user_id, group_id, session):
        st = orm.user_group.delete().where(orm.user_group.c.user_id == user_id).where(orm.user_group.c.group_id == group_id)
        session.execute(st)
        self.log.notice(f"User {user_id} removed from group {group_id}")

    def _create_user(self, username, display_name, email, password, session, skip_check=False):
        user = orm.User(
            username=username,
            display=display_name,
            email=email,
        )
        self._set_password(user, password, skip_check)
        session.add(user)
        self.log.notice(f"User {username} created")
        return user

    def view_user_page(self, user_id):
        with self.db as session:
            user = session.query(orm.User).filter_by(id=user_id).first()
            if not user:
                return flask.abort(404)
            return flask.render_template("user.html", user=user, title=user.username, actions=self._build_action_list(user, False))

    def edit_user_form(self, user_id):
        with self.db as session:
            user = session.query(orm.User).filter_by(id=user_id).first()
            if not user:
                return flask.abort(404)
            form = EditUserForm(user=user)
            if form.validate_on_submit():
                ue = session.query(orm.User.id).filter_by(email=form.email.data).first()
                if ue and not user.id == ue.id:
                    flasht("pipeman.auth_db.error.email_already_exists", "error")
                    self.log.warning(f"Email on edit for {user_id} conflicts with {ue.id}")
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
                    flasht("pipeman.auth_db.page.edit_user.success", "success")
                    return flask.redirect(flask.url_for("users.view_user", user_id=user_id))
            return flask.render_template(
                "form.html",
                form=form,
                title=gettext("pipeman.auth_db.page.edit_user.title")
            )

    def reset_password_form(self, user_id):
        with self.db as session:
            user = session.query(orm.User).filter_by(id=user_id).first()
            if not user:
                return flask.abort(404)
            form = ConfirmationForm()
            if form.validate_on_submit():
                new_password = self._reset_password(user)
                session.commit()
                flasht("pipeman.auth_db.page.reset_password.success", "success", password=new_password)
                return flask.redirect(flask.url_for("users.view_user", user_id=user_id))
            return flask.render_template("form.html", form=form, title=gettext("pipeman.auth_db.page.reset_password.title"), instructions=gettext("pipeman.auth_db.page.reset_password.instructions"))

    def set_password_cli(self, username, password):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                raise UserInputError("pipeman.auth_db.error.user_does_not_exist")
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
        user.phash = self.sh.hash_secret(password, user.salt)
        self.log.notice(f"Password updated for {user.username}")

    def unlock_user_account(self, username):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if user:
                user.locked_until = None
            st = sa.update(orm.UserLoginRecord).where(orm.UserLoginRecord.username == username).where(orm.UserLoginRecord.was_since_last_clear == True).values(was_since_last_clear=False)
            session.execute(st)
            session.commit()
            self.log.notice(f"User account {username} unlocked")


class CreateUserForm(PipemanFlaskForm):

    oc: OrganizationController = None

    username = wtf.StringField(
        DelayedTranslationString("pipeman.label.user.username"),
        validators=[
            wtfv.InputRequired(
                message=DelayedTranslationString("pipeman.error.required_field")
            )
        ]
    )

    display = wtf.StringField(
        DelayedTranslationString("pipeman.label.user.display_name"),
        validators=[
            wtfv.InputRequired(
                message=DelayedTranslationString("pipeman.error.required_field")
            )
        ]
    )

    email = wtf.EmailField(
        DelayedTranslationString("pipeman.label.user.email"),
        validators=[
            wtfv.InputRequired(
                message=DelayedTranslationString("pipeman.error.required_field")
            )
        ]
    )

    groups = wtf.SelectMultipleField(
        DelayedTranslationString("pipeman.label.user.groups"),
        coerce=int,
        widget=Select2Widget(allow_multiple=True, placeholder=DelayedTranslationString("pipeman.common.placeholder"))
    )
    organizations = wtf.SelectMultipleField(
        DelayedTranslationString("pipeman.label.user.organizations"),
        coerce=int,
        widget=Select2Widget(allow_multiple=True, placeholder=DelayedTranslationString("pipeman.common.placeholder"))
    )

    submit = wtf.SubmitField("pipeman.common.submit")

    @injector.construct
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_list = groups_select()
        self.groups.choices = self.group_list
        self.organizations.choices = self.oc.list_organizations(include_global=False)


class EditUserForm(PipemanFlaskForm):

    oc: OrganizationController = None

    display = wtf.StringField(
        DelayedTranslationString("pipeman.label.user.display_name"),
        validators=[
            wtfv.InputRequired(
                message=DelayedTranslationString("pipeman.error.required_field")
            )
        ]
    )

    email = wtf.EmailField(
        DelayedTranslationString("pipeman.label.user.email"),
        validators=[
            wtfv.InputRequired(
                message=DelayedTranslationString("pipeman.error.required_field")
            )
        ]
    )

    groups = wtf.SelectMultipleField(
        DelayedTranslationString("pipeman.label.user.groups"),
        coerce=int,
        widget=Select2Widget(allow_multiple=True, placeholder=DelayedTranslationString("pipeman.common.placeholder"))
    )
    
    organizations = wtf.SelectMultipleField(
        DelayedTranslationString("pipeman.label.user.organizations"),
        coerce=int,
        widget=Select2Widget(allow_multiple=True, placeholder=DelayedTranslationString("pipeman.common.placeholder"))
    )

    submit = wtf.SubmitField(DelayedTranslationString("pipeman.common.submit"))

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
        self.org_list = self.oc.list_organizations(include_global=False)
        self.organizations.choices = self.org_list


class EditMyselfForm(PipemanFlaskForm):

    display = wtf.StringField(
        DelayedTranslationString("pipeman.label.user.display_name"),
        validators=[
            wtfv.InputRequired(
                message=DelayedTranslationString("pipeman.error.required_field")
            )
        ]
    )

    submit = wtf.SubmitField(DelayedTranslationString("pipeman.common.submit"))

    def __init__(self, *args, user=None, **kwargs):
        if user:
            kwargs['display'] = user.display
        super().__init__(*args, **kwargs)


class ChangePasswordForm(PipemanFlaskForm):

    password = wtf.PasswordField(
        DelayedTranslationString("pipeman.label.user.password"),
        validators=[
            wtfv.InputRequired(
                message=DelayedTranslationString("pipeman.error.required_field")
            )
        ]
    )

    repeat_password = wtf.PasswordField(
        DelayedTranslationString("pipeman.label.user.repeat_password"),
        validators=[
            wtfv.EqualTo(
                "password",
                message=DelayedTranslationString("pipeman.error.fields_must_match")
            )
        ]
    )

    submit = wtf.SubmitField(DelayedTranslationString("pipeman.common.submit"))


class DatabaseEntityAuthenticationManager(FormAuthenticationManager):

    sh: SecurityHelper = None
    cfg: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self, form_template_name: str = "form.html"):
        super().__init__(form_template_name)
        self.log = zrlog.get_logger("pipeman.auth_db")
        self._max_failed_logins = self.cfg.as_int(("pipeman", "auth_db", "max_failed_logins"), 5)
        self._max_failed_login_window = self.cfg.as_int(("pipeman", "auth_db", "failed_login_window_hours"), 24)
        self._lockout_time = self.cfg.as_int(("pipeman", "auth_db", "failed_login_lockout_time"), 24)

    @injector.inject
    def load_user(self, username, db: Database = None):
        with db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if user:
                return self._build_user(user, session)
        return None

    def _record_login_attempt(self, username, from_api, error_message=None, is_lockable_error: bool = None, create_record: bool = True, session=None):
        if error_message:
            if is_lockable_error is None:
                is_lockable_error = True
            self.log.warning(f"invalid login attempt {username}, {'yes' if from_api else 'no'}, {error_message}")
        else:
            is_lockable_error = False
            self.log.out(f"successful login attempt {username}, {'yes' if from_api else 'no'}")
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
                self.log.warning(f"User has too many recent logins, locking account {user.username}")
                user.locked_until = datetime.datetime.now() + datetime.timedelta(hours=self._lockout_time)
                session.commit()
                flasht("pipeman.auth_db.error.too_many_recent_logins", "error")

    def _clear_login_records(self, username, session):
        self.log.info(f"Clearing old logins for old {username}")
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
            flasht("pipeman.auth_db.error.account_locked", "warning")
            self._record_login_attempt(username, from_api, "locked", False, False)
            return None
        if from_api and not user.allowed_api_access:
            self._record_login_attempt(username, from_api, "no api access allowed", False)
            return None
        return user

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
                    return self._build_user(user, session)
            if key.old_expiry > gate_date:
                error = "invalid api token"
                if self.sh.check_secret(auth_header, key.old_key_salt, key.old_key_hash):
                    self._record_login_attempt(username, True, session=session)
                    if self.sh.is_hash_outdated(auth_header, key.old_key_salt, key.old_key_hash):
                        key.old_key_hash = self.sh.hash_secret(auth_header, key.old_key_salt)
                        session.commit()
                    return self._build_user(user, session)
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

    def _build_user(self, user, session):
        permissions = set()
        for group in user.groups:
            permissions.update(group.permissions.split(";"))
        organizations = [x.id for x in user.organizations]
        datasets = [x.id for x in user.datasets]
        props = json.loads(user.properties) if user.properties else {}
        props['last_success'] = datetime.datetime.strptime(props['last_success'], "%Y-%m-%d %H:%M:%S") if 'last_success' in props and props['last_success'] else None
        props['last_error'] = datetime.datetime.strptime(props['last_error'], "%Y-%m-%d %H:%M:%S") if 'last_error' in props and props['last_error'] else None
        return AuthenticatedUser(
            user.id,
            user.username,
            user.display,
            permissions,
            organizations,
            datasets,
            **props
        )
