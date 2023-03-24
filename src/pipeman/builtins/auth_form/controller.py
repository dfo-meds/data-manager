"""Supporting controller and tools for form-based authentication."""
from pipeman.auth.auth import AuthenticationManager
import flask_login as fl
from flask_wtf import FlaskForm
import wtforms as wtf
import wtforms.validators as wtfv
from pipeman.i18n import DelayedTranslationString
from pipeman.i18n import gettext
import flask


class LoginForm(FlaskForm):
    """Form for logging in."""

    username = wtf.StringField(
        DelayedTranslationString("pipeman.auth_form.username"),
        validators=[
            wtfv.InputRequired(message=DelayedTranslationString("pipeman.auth_form.missing_username"))
        ]
    )
    password = wtf.PasswordField(
        DelayedTranslationString("pipeman.auth_form.password"),
        validators=[
            wtfv.InputRequired(message=DelayedTranslationString("pipeman.auth_form.missing_password"))
        ]
    )

    submit = wtf.SubmitField(DelayedTranslationString("pipeman.general.submit"))


class FormAuthenticationManager(AuthenticationManager):
    """Authentication manager that provides and handles the form responses.

    Specific sub-classes are necessary to handle finding and loading the user.
    """

    def __init__(self, form_template_name: str = "form.html"):
        super().__init__()
        self.template = form_template_name

    def login_handler(self):
        """Handle a login request by displaying and handling the form."""
        form = LoginForm()
        if form.validate_on_submit():
            user = self.attempt_login(form.username.data, form.password.data)
            if user:
                fl.login_user(user)
                flask.flash(str(gettext("pipeman.auth_form.login_success")), "success")
                return self.login_success()
            else:
                flask.flash(str(gettext("pipeman.auth_form.login_error")), "error")
        return flask.render_template(
            self.template,
            form=form,
            title=gettext("pipeman.auth_form.login.title")
        )

    def logout_handler(self):
        """Handle the logout for Flask login."""
        fl.logout_user()
        flask.session.modified = True
        for k, v in flask.session.items():
            print(f"{k}: {v}")
        flask.flash(str(gettext("pipeman.auth_form.logout_success")), "success")
        return self.logout_success()

    def attempt_login(self, username: str, password: str):
        """Attempt to perform a login."""
        raise NotImplementedError()

    def load_user(self, username):
        """Load a user from their username."""
        raise NotImplementedError()
