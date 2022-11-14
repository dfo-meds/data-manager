from pipeman.auth.auth import AuthenticationManager
import flask_login as fl
from flask_wtf import FlaskForm
import wtforms as wtf
import wtforms.validators as wtfv
import flask


class LoginForm(FlaskForm):

    username = wtf.StringField()
    password = wtf.PasswordField()


class FormAuthenticationManager(AuthenticationManager):

    def __init__(self):
        super().__init__()
        self.template = self.config.as_str(("pipeman", "authentication", "form_template"), default="form.html")

    def login_handler(self):
        form = LoginForm()
        if form.validate_on_submit():
            user = self.find_user(form.username.data, form.password.data)
            if user:
                fl.login_user(user)
                return self.login_success()
            else:
                #TODO: Translate
                flask.flash("Invalid username or password")
        return flask.render_template(self.template, form=form)

    def logout_handler(self):
        fl.logout_user()
        #TODO: Translate
        flask.flash("User logged out successfully")
        return self.logout_success()

    def load_user(self, username):
        raise NotImplementedError()

    def find_user(self, username, password):
        raise NotImplementedError()

