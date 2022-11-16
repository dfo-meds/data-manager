from pipeman.auth.auth import AuthenticationManager
import flask_login as fl
from flask_wtf import FlaskForm
import wtforms as wtf
import wtforms.validators as wtfv
from pipeman.i18n import DelayedTranslationString as Dts
from pipeman.i18n import gettext
import flask


class LoginForm(FlaskForm):

    username = wtf.StringField(Dts("pipeman.plugins.auth_form.username"))
    password = wtf.PasswordField(Dts("pipeman.plugins.auth_form.password"))
    submit = wtf.SubmitField(Dts("pipeman.plugins.auth_form.submit"))


class FormAuthenticationManager(AuthenticationManager):

    def __init__(self, form_template_name="form.html"):
        super().__init__()
        self.template = form_template_name

    def login_handler(self):
        form = LoginForm()
        if form.validate_on_submit():
            user = self.find_user(form.username.data, form.password.data)
            if user:
                fl.login_user(user)
                return self.login_success()
            else:
                flask.flash(gettext("pipeman.plugins.auth_form.login_error"), "error")
        return flask.render_template(self.template, form=form)

    def logout_handler(self):
        fl.logout_user()
        flask.flash(gettext("pipeman.plugins.auth_form.login_success"), "success")
        return self.logout_success()

    def load_user(self, username):
        raise NotImplementedError()

    def find_user(self, username, password):
        raise NotImplementedError()

