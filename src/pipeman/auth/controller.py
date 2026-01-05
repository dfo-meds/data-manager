from pipeman.auth import SecurityHelper
from pipeman.db.db import Database
from autoinject import injector
import pipeman.db.orm as orm
from pipeman.util.flask import ConfirmationForm, ActionList, Select2Widget, RequestInfo
from pipeman.i18n import gettext, DelayedTranslationString, TranslationManager
import flask
import flask_login
import wtforms as wtf
import wtforms.validators as wtfv
from pipeman.util.errors import UserInputError
from pipeman.auth.util import groups_select
from pipeman.org import OrganizationController
import datetime
import zrlog
import sqlalchemy as sa
from pipeman.util.flask import DataQuery, DataTable, DatabaseColumn, ActionListColumn, flasht, PipemanFlaskForm
from pipeman.email import EmailController


@injector.injectable
class DatabaseUserController:

    db: Database = None
    sh: SecurityHelper = None
    emails: EmailController = None

    @injector.construct
    def __init__(self):
        self.log = zrlog.get_logger("pipeman.auth")

    def set_api_access(self, username, is_enabled: bool):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                raise UserInputError("pipeman.auth.error.user_does_not_exist")
            user.allowed_api_access = is_enabled
            session.commit()
            self.log.notice(f"API access for {username} set to {is_enabled}")

    def create_api_key(self, username, display, expiry_days):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                raise UserInputError("pipeman.auth.error.user_does_not_exist")
            prefix = self.sh.generate_secret(32)
            raw_key = self.sh.generate_secret(64)
            key_salt = self.sh.generate_salt()
            auth_header = self.sh.build_auth_header(prefix, raw_key, user.username)
            key_hash = self.sh.hash_secret(raw_key, key_salt)
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
                raise UserInputError("pipeman.auth.error.user_does_not_exist")
            key = session.query(orm.APIKey).filter_by(user_id=user.id, prefix=prefix).first()
            if not key:
                raise UserInputError("pipeman.auth.error.api_key_does_not_exist")
            raw_key = self.sh.generate_secret(64)
            key_salt = self.sh.generate_salt()
            auth_header = self.sh.build_auth_header(prefix, raw_key, user.username)
            key_hash = self.sh.hash_secret(raw_key, key_salt)
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
                title=gettext("pipeman.auth.page.view_myself.title", username=user.username)
            )

    def edit_myself_form(self):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=flask_login.current_user.get_id()).first()
            form = EditMyselfForm(user=user)
            if form.validate_on_submit():
                user.display = form.display.data
                user.language_preference = form.language_preference.data
                session.commit()
                flasht("pipeman.auth.page.edit_myself.success", 'success')
                return flask.redirect(flask.url_for("users.view_myself"))
            return flask.render_template("form.html", form=form, title=gettext("pipeman.auth.page.edit_myself.title"))

    def change_password_form(self):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=flask_login.current_user.get_id()).first()
            if user.phash is None:
                flasht("pipeman.auth.page.change_password.error_no_password_for_account")
                return flask.redirect(flask.url_for("users.view_myself"))
            form = ChangePasswordForm()
            if form.validate_on_submit():
                try:
                    self._set_password(user, form.password.data)
                    flasht("pipeman.auth.page.change_password.success", 'success')
                    return flask.redirect(flask.url_for("users.view_myself"))
                except UserInputError as ex:
                    flask.flash(str(ex), "error")
            return flask.render_template(
                "form.html", 
                form=form, 
                title=gettext("pipeman.auth.page.change_password.title"),
                instructions=gettext("pipeman.auth.page.change_password.instructions")
            )

    def list_users_page(self):
        links = []
        if flask_login.current_user.has_permission("auth_db.create"):
            links.append((
                flask.url_for("users.create_user"),
                gettext("pipeman.auth.page.create_user.link")
            ))
        return flask.render_template(
            "data_table.html",
            table=self._users_table(),
            side_links=links,
            title=gettext("pipeman.auth.page.list_users.title"),
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
            actions.add_action('pipeman.auth.page.view_user.link', 'users.view_user', **kwargs)
        if flask_login.current_user.has_permission("auth_db.edit"):
            actions.add_action('pipeman.auth.page.edit_user.link', 'users.edit_user', **kwargs)
        if flask_login.current_user.has_permission("auth_db.reset"):
            actions.add_action('pipeman.auth.page.reset_password.link', 'users.reset_password', **kwargs)
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
                    flasht("pipeman.auth.error.username_already_exists", "error")
                    self.log.warning(f"New user username conflicts with {u.id}")
                elif ue:
                    flasht("pipeman.auth.error.email_already_exists", "error")
                    self.log.warning(f"New user email conflicts with {ue.id}")
                else:
                    pw = self.sh.random_password()
                    user = self._create_user(
                        form.username.data,
                        form.display.data,
                        form.email.data,
                        pw,
                        form.language_preference.data,
                        session,
                        True
                    )
                    session.commit()
                    for group_id in form.groups.data:
                        self._assign_to_group(user.id, group_id, session)
                    for org_id in form.organizations.data:
                        self._assign_to_org(user.id, org_id, session)
                    session.commit()
                    flasht("pipeman.auth.page.create_user.success", "success", password=pw)
                    return flask.redirect(flask.url_for("users.view_user", user_id=user.id))
        return flask.render_template("form.html", form=form, title=gettext("pipeman.auth.page.create_user.title"))

    def _send_password_email(self, user, new_password):
        if self.emails.send_template("password_update", user.language_preference, user.email, new_password=new_password, display_name=user.display):
            flasht("pipeman.auth.message.email_send_success", "success")
            return True
        return False

    def create_user_cli(self, username, email, display, password, lang_pref: str = "en", no_email: bool = False):
        skip_check = False
        if password is None:
            password = self.sh.random_password()
            skip_check = True
        with self.db as session:
            u = session.query(orm.User.id).filter_by(username=username).first()
            if u:
                raise UserInputError("pipeman.auth.error.username_already_exists")
            ue = session.query(orm.User.id).filter_by(email=email).first()
            if ue:
                raise UserInputError("pipeman.auth.error.email_already_exists")
            user = self._create_user(username, display, email, password, lang_pref, session, skip_check)
            session.commit()
            if not no_email:
                self._send_password_email(user, password)

    def create_user_from_external(self, username, email, display, roles) -> str:
        with self.db as session:
            u = session.query(orm.User).filter_by(username=username).first()
            if u:
                u.display = display
                self._update_user_roles_from_external(u, session, roles)
                session.commit()
                return u.username
            ue = session.query(orm.User).filter_by(email=email).first()
            if ue:
                u.display = display
                self._update_user_roles_from_external(ue, session, roles)
                session.commit()
                return u.username
            user = self._create_user(username, display, email, None, "en", session, True)
            self._update_user_roles_from_external(user, session, roles)
            session.commit()
            return username

    def _update_user_roles_from_external(self, user, session, roles):
        if not roles:
            return
        orgs = set()
        groups = set()
        for x in roles:
            if x.startswith('group.'):
                groups.add(x[6:])
            elif x.startswith("organization."):
                orgs.add(x[13:])
            else:
                self.log.warning(f"Unrecognized application role {x}")
        if orgs:
            self._update_user_orgs_from_external(user, session, orgs)
        if groups:
            self._update_user_groups_from_external(user, session, groups)

    def _update_user_orgs_from_external(self, user, session, orgs):
        st = orm.user_organization.delete().where(orm.user_organization.c.user_id == user.id)
        session.execute(st)
        for org_name in orgs:
            org = session.query(orm.Organization).filter_by(short_name=org_name).first()
            if org:
                st = orm.user_organization.insert().values({
                    "user_id": user.id,
                    "organization_id": org.id
                })
                session.execute(st)
            else:
                self.log.warning(f"Could not find organization {org_name}, skipped")

    def _update_user_groups_from_external(self, user, session, groups):
        st = orm.user_group.delete().where(orm.user_group.c.user_id == user.id)
        session.execute(st)
        for group_name in groups:
            group = session.query(orm.Group).filter_by(short_name=group_name).first()
            if group:
                st = orm.user_group.insert().values({
                    "user_id": user.id,
                    "group_id": group.id
                })
                session.execute(st)
            else:
                self.log.warning(f"Could not find group {group_name}, skipped")

    def assign_to_org_cli(self, org_name, username):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                raise UserInputError("pipeman.auth.error.user_does_not_exist")
            org = session.query(orm.Organization).filter_by(short_name=org_name).first()
            if not org:
                raise UserInputError("pipeman.org.error.org_does_not_exist")
            self._assign_to_org(user.id, org.id, session)
            session.commit()

    def remove_from_org_cli(self, org_name, username):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                raise UserInputError("pipeman.auth.error.user_does_not_exist")
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
                raise UserInputError("pipeman.auth.error.user_does_not_exist")
            group = session.query(orm.Group).filter_by(short_name=group_name).first()
            if not group:
                raise UserInputError("pipeman.auth.error.group_does_not_exist")
            self._assign_to_group(user.id, group.id, session)
            session.commit()

    def remove_from_group_cli(self, group_name, username):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                raise UserInputError("pipeman.auth.error.user_does_not_exist")
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

    def _create_user(self, username, display_name, email, password, language_preference, session, skip_check=False):
        user = orm.User(
            username=username,
            display=display_name,
            email=email,
            language_preference=language_preference
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
                    flasht("pipeman.auth.error.email_already_exists", "error")
                    self.log.warning(f"Email on edit for {user_id} conflicts with {ue.id}")
                else:
                    user.email = form.email.data
                    user.display = form.display.data
                    user.language_preference = form.language_preference.data
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
                    flasht("pipeman.auth.page.edit_user.success", "success")
                    return flask.redirect(flask.url_for("users.view_user", user_id=user_id))
            return flask.render_template(
                "form.html",
                form=form,
                title=gettext("pipeman.auth.page.edit_user.title")
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
                self._send_password_email(user, new_password)
                flasht("pipeman.auth.page.reset_password.success", "success", password=new_password)
                return flask.redirect(flask.url_for("users.view_user", user_id=user_id))
            return flask.render_template("form.html", form=form, title=gettext("pipeman.auth.page.reset_password.title"), instructions=gettext("pipeman.auth.page.reset_password.instructions"))

    def set_password_cli(self, username, password):
        with self.db as session:
            user = session.query(orm.User).filter_by(username=username).first()
            if not user:
                raise UserInputError("pipeman.auth.error.user_does_not_exist")
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
        if password is None:
            user.phash = None
        else:
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
    tm: TranslationManager = None

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

    language_preference = wtf.SelectField(
        DelayedTranslationString("pipeman.label.user.language_preference"),
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.group_list = groups_select()
        self.groups.choices = self.group_list
        self.organizations.choices = self.oc.list_organizations(include_global=False)
        self.language_preference.choices = [
            (x, gettext(f"languages.full.{x}"))
            for x in self.tm.supported_languages()
            if x != "und"
        ]


class EditUserForm(PipemanFlaskForm):

    oc: OrganizationController = None
    tm: TranslationManager = None

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

    language_preference = wtf.SelectField(
        DelayedTranslationString("pipeman.label.user.language_preference"),
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
        self.language_preference.choices = [
            (x, gettext(f"languages.full.{x}"))
            for x in self.tm.supported_languages()
            if x != "und"
        ]


class EditMyselfForm(PipemanFlaskForm):

    tm: TranslationManager = None

    display = wtf.StringField(
        DelayedTranslationString("pipeman.label.user.display_name"),
        validators=[
            wtfv.InputRequired(
                message=DelayedTranslationString("pipeman.error.required_field")
            )
        ]
    )

    language_preference = wtf.SelectField(
        DelayedTranslationString("pipeman.label.user.language_preference"),
        validators=[
            wtfv.InputRequired(
                message=DelayedTranslationString("pipeman.error.required_field")
            )
        ]
    )

    submit = wtf.SubmitField(DelayedTranslationString("pipeman.common.submit"))

    @injector.construct
    def __init__(self, *args, user=None, **kwargs):
        if user:
            kwargs['display'] = user.display
        super().__init__(*args, **kwargs)
        self.language_preference.choices = [
            (x, gettext(f"languages.full.{x}"))
            for x in self.tm.supported_languages()
            if x != "und"
        ]


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

