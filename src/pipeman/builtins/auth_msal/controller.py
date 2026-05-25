"""Supporting controller and tools for form-based authentication."""
from pipeman.auth.auth import AuthenticationHandler
from pipeman.util.flask import flasht
from pipeman.i18n import gettext
import flask
from pipeman.i18n import LanguageDetector, TranslationManager
import msal
from autoinject import injector
from pipeman.auth.controller import DatabaseUserController
import pipeman


class AzureAuthenticationHandler(AuthenticationHandler):
    """Authentication manager that provides and handles the form responses.

    Specific sub-classes are necessary to handle finding and loading the user.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._scopes = self.config.as_list(("pipeman", "auth", "msal", "scopes"), default=["email"])
        self._prompts = self.config.as_str(("pipeman", "auth", "msal", "prompt"), default=None)
        self._domain_hint = self.config.as_str(("pipeman", "auth", "msal", "domain_hint"), default=None)
        self._max_age = self.config.as_int(("pipeman", "auth", "msal", "max_age"), default=None)
        self._args = {
            "client_id": self.config.as_str(("pipeman", "auth", "msal", "client_id")),
            "authority": self.config.as_str(("pipeman", "auth", "msal", "authority")),
            "app_name": self.config.as_str(("pipeman", "auth", "msal", "app_name"), default="pipeman"),
            "app_version": self.config.as_str(("pipeman", "auth", "msal", "app_version"), default=pipeman.__version__),
        }
        if self.config.is_truthy(("pipeman", "auth", "msal", "client_secret")):
            self._args['client_credential'] = self.config.as_str(("pipeman", "auth", "msal", "client_secret"))
        elif self.config.is_truthy(("pipeman", "auth", "msal", "private_key")):
            self._args['client_credential'] = self.config.as_str(("pipeman", "auth", "msal", "thumbprint"))
            with open(self.config.as_path(("pipeman", "auth", "msal", "private_key")), "r") as h:
                self._args["private_key"] = h.read()
        self._msal_app = None

    def _ensure_app(self):
        if self._msal_app is None:
            self._msal_app = msal.ConfidentialClientApplication(
                **self._args
            )

    def display_name(self):
        return gettext("pipeman.login.msal")

    @injector.inject
    def login_page(self, ld: LanguageDetector = None, tm: TranslationManager = None):
        """Handle a login request by displaying and handling the form."""
        args = {
            "scopes": self._scopes,
            "redirect_uri": self._auth_manager.redirect_handler_url(),
            "response_mode": "form_post",
        }
        if self._prompts is not None:
            args["prompt"] = self._prompts
        if self._domain_hint is not None:
            args["domain_hint"] = self._domain_hint
        if self._max_age is not None:
            args["max_age"] = self._max_age
        self._ensure_app()
        response = self._msal_app.initiate_auth_code_flow(
            **args
        )
        flask.session["_msal_login"] = response
        return self._auth_manager.redirect_for_login(response['auth_uri'], self._handler_name)

    def login_from_redirect(self):
        original = flask.session["_msal_login"]
        if '_msal_login' not in flask.session or 'auth_uri' not in flask.session['_msal_login']:
            flasht("pipeman.auth_msal.page.login.error_no_original")
            return flask.redirect(flask.url_for("auth.login"))
        if 'error' in flask.request.args:
            flasht("pipeman.auth_msal.page.login.msal_error")
            self._log.warning(f"{flask.request.args['error']}: {flask.request.args['error_description']}")
            return flask.redirect(flask.url_for("auth.login"))
        response = None
        if 'code' in flask.request.args:
            response = flask.request.args.to_dict()
        elif 'code' in flask.request.form:
            response = flask.request.form.to_dict()
        else:
            flasht("pipeman.auth_msal.page.login.error_no_response")
            return flask.redirect(flask.url_for("auth.login"))
        try:
            self._ensure_app()
            token = self._msal_app.acquire_token_by_auth_code_flow(
                auth_response=response,
                auth_code_flow=original,
                scopes=self._scopes
            )
        except RuntimeError as ex:
            flasht("pipeman.auth_msal.page.login.error_token_acquisition")
            self._log.exception("Error while acquiring MSAL token")
            return flask.redirect(flask.url_for("auth.login"))
        return self._create_and_login_account(
            token['id_token_claims']['email'],
            token['id_token_claims']['preferred_username'] if 'preferred_username' in token['id_token_claims'] else None,
            token['id_token_claims']['name'] if 'name' in token['id_token_claims'] else None,
            token['id_token_claims']['roles'] if 'roles' in token['id_token_claims'] else None
        )

    @injector.inject
    def _create_and_login_account(self, email, username=None, display_name=None, duc: DatabaseUserController = None, roles = None):
        if username is None:
            username = email
        if display_name is None:
            display_name = username
        username = duc.create_user_from_external(username, email, display_name, roles)
        return self._auth_manager.login_user(username, self._handler_name)
