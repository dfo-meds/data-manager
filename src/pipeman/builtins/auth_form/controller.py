"""Supporting controller and tools for form-based authentication."""
from pipeman.auth.auth import AuthenticationManager
import flask_login as fl
from pipeman.util.flask import PipemanFlaskForm as FlaskForm
import wtforms as wtf
import wtforms.validators as wtfv
from pipeman.i18n import DelayedTranslationString
from pipeman.i18n import gettext
import flask
from pipeman.util.flask import NoControlCharacters, PipemanFlaskForm
from pipeman.util.setup import invalidate_session


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
                invalidate_session()
                fl.login_user(user)
                flask.flash(str(gettext("pipeman.auth_form.page.login.success")), "success")
                return self.login_success()
            else:
                flask.flash(str(gettext("pipeman.auth_form.page.login.error")), "error")
        return flask.render_template(
            self.template,
            form=form,
            title=gettext("pipeman.auth_form.page.login.title")
        )

    def logout_handler(self):
        """Handle the logout for Flask login."""
        invalidate_session()
        fl.logout_user()
        flask.flash(str(gettext("pipeman.auth_form.page.logout.success")), "success")
        return self.logout_success()

    def attempt_login(self, username: str, password: str):
        """Attempt to perform a login."""
        raise NotImplementedError()

    def load_user(self, username):
        """Load a user from their username."""
        raise NotImplementedError()
