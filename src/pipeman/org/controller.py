from autoinject import injector
from pipeman.db import Database
import pipeman.db.orm as orm
from pipeman.i18n import gettext
from pipeman.util.errors import UserInputError
import logging
import flask_login
from pipeman.i18n import DelayedTranslationString, MultiLanguageString
import json
import flask
from flask_wtf import FlaskForm
import wtforms.validators as wtfv
import wtforms as wtf
from pipeman.util.flask import TranslatableField, ActionList, flasht


@injector.injectable
class OrganizationController:

    db: Database = None

    @injector.construct
    def __init__(self):
        pass

    def list_organizations_page(self):
        with self.db as session:
            query = session.query(orm.Organization)
            create_link = None
            if flask_login.current_user.has_permission("organizations.create"):
                create_link = flask.url_for("core.create_organization")
            return flask.render_template(
                "list_organizations.html",
                organizations=self._iterate_organizations(query),
                title=gettext("pipeman.org.page.list_organizations.title"),
                create_link=create_link
            )

    def view_organization_page(self, org_id):
        with self.db as session:
            org = session.query(orm.Organization).filter_by(id=org_id).first()
            if not org:
                return flask.abort(404)
            display_name = MultiLanguageString(json.loads(org.display_names)) if org.display_names else gettext("pipeman.common.na")
            return flask.render_template(
                "view_organization.html",
                org=org,
                display=display_name,
                title=gettext('pipeman.org.page.view_organization.title'),
                actions=self._build_action_list(org, False)
            )

    def _build_action_list(self, org, short_list: bool = True):
        actions = ActionList()
        kwargs = {"org_id": org.id}
        if short_list:
            actions.add_action('pipeman.org.page.view_organization.link', 'core.view_organization', **kwargs)
        if flask_login.current_user.has_permission("organizations.edit"):
            actions.add_action("pipeman.org.page.edit_organization.link", "core.edit_organization", **kwargs)
        return actions

    def _iterate_organizations(self, query):
        for org in query:
            actions = self._build_action_list(org, True)
            yield org, MultiLanguageString(json.loads(org.display_names) if org.display_names else {"und": org.short_name}), actions

    def create_organization_page(self):
        form = OrganizationForm()
        if form.validate_on_submit():
            org_id = self.upsert_organization(form.short_name.data, form.display_names.data)
            flasht("pipeman.org.page.create_organization.success", 'success')
            return flask.redirect(flask.url_for('core.view_organization', org_id=org_id))
        return flask.render_template('form.html', form=form, title=gettext('pipeman.org.page.create_organization.title'))

    def edit_organization_form(self, org_id):
        with self.db as session:
            org = session.query(orm.Organization).filter_by(id=org_id).first()
            form = OrganizationForm(org=org)
            if form.validate_on_submit():
                org_id = self.upsert_organization(form.short_name.data, form.display_names.data, org.id)
                flasht("pipeman.org.page.edit_organization.success", "success")
                return flask.redirect(flask.url_for('core.view_organization', org_id=org_id))
            return flask.render_template('form.html', form=form, title=gettext('pipeman.org.page.edit_organization.title'))

    def upsert_organization(self, org_name, display_names=None, org_id=None):
        with self.db as session:
            org = None
            if org_id:
                org = session.query(orm.Organization).filter_by(id=org_id).first()
            check_org = session.query(orm.Organization).filter_by(short_name=org_name).first()
            if check_org and (org_id is None or not check_org.id == org.id):
                raise UserInputError("pipeman.org.error.org_already_exists")
            if org:
                if display_names:
                    org.display_names = json.dumps(display_names)
            else:
                org = orm.Organization(
                    short_name=org_name,
                    display_names=json.dumps(display_names if display_names else {})
                )
                session.add(org)
            session.commit()
            logging.getLogger("pipeman.org").out(f"Organization {org_name} created")
            return org.id

    def list_organizations(self):
        with self.db as session:
            all_access = flask_login.current_user.has_permission("organizations.manage.any")
            global_access = flask_login.current_user.has_permission("organizations.manage.global")
            orgs = []
            if global_access:
                orgs.append((0, DelayedTranslationString("pipeman.label.org.global_name")))
            for org in session.query(orm.Organization):
                if all_access or flask_login.current_user.belongs_to(org.id):
                    orgs.append((org.id, MultiLanguageString(json.loads(org.display_names) if org.display_names else {'und': org.short_name})))
            return orgs


class OrganizationForm(FlaskForm):

    short_name = wtf.StringField(
        DelayedTranslationString("pipeman.label.org.short_name"),
        validators=[
            wtfv.DataRequired(
                message=DelayedTranslationString("pipeman.error.required_field")
            )
        ]
    )

    display_names = TranslatableField(wtf.StringField, label=DelayedTranslationString("pipeman.common.display_name"))

    submit = wtf.SubmitField(DelayedTranslationString("pipeman.common.submit"))

    def __init__(self, *args, org=None, **kwargs):
        self.org = org
        if self.org:
            kwargs["short_name"] = org.short_name
            kwargs["display_names"] = json.loads(org.display_names) if org.display_names else {}
        super().__init__(*args, **kwargs)
