"""Routes for the authentication system"""
import flask_login as fl
from autoinject import injector
from pipeman.auth.auth import AuthenticationManager
from pipeman.auth import require_permission
from pipeman.util.flask import MultiLanguageBlueprint
from .controller import DatabaseUserController

auth = MultiLanguageBlueprint("auth", __name__)
users = MultiLanguageBlueprint("users", __name__)


@auth.i18n_route("/login", methods=["GET", "POST"])
@injector.inject
def login(am: AuthenticationManager = None):
    """Login handler"""
    if fl.current_user.is_authenticated:
        return am.login_success()
    return am.login_page()


@auth.i18n_route("/login/<method>", methods=["GET", "POST"])
@injector.inject
def login_method(method, am: AuthenticationManager = None):
    """Login for specific method"""
    if fl.current_user.is_authenticated:
        return am.login_success()
    return am.login_page_for_handler(method)


@auth.route("/api/login-from-redirect", methods=["GET", "POST"])
@injector.inject
def login_by_redirect(am: AuthenticationManager = None):
    return am.login_from_redirect()


@auth.i18n_route("/logout", methods=["GET", "POST"])
@injector.inject
def logout(am: AuthenticationManager = None):
    """Logout handler"""
    if not fl.current_user.is_authenticated:
        return am.logout_success()
    return am.logout_page()


@auth.route("/api/refresh", methods=['GET'])
def refresh_session():
    """Refresh session"""
    return {}


@users.i18n_route("/me")
@require_permission("_is_not_anonymous")
@injector.inject
def view_myself(duc: DatabaseUserController = None):
    return duc.view_myself_page()


@users.i18n_route("/me/edit", methods=['GET', 'POST'])
@require_permission("_is_not_anonymous")
@injector.inject
def edit_myself(duc: DatabaseUserController = None):
    return duc.edit_myself_form()


@users.i18n_route("/me/change-password", methods=['GET', 'POST'])
@require_permission("_is_not_anonymous")
@injector.inject
def change_my_password(duc: DatabaseUserController = None):
    return duc.change_password_form()


@users.i18n_route("/users")
@require_permission("auth_db.view.all")
@injector.inject
def list_users(duc: DatabaseUserController = None):
    return duc.list_users_page()


@users.route("/api/users-ajax", methods=["POST", "GET"])
@require_permission("auth_db.view.all")
@injector.inject
def list_users_ajax(duc: DatabaseUserController = None):
    return duc.list_users_ajax()


@users.i18n_route("/users/create", methods=['GET', 'POST'])
@require_permission("auth_db.create")
@injector.inject
def create_user(duc: DatabaseUserController = None):
    return duc.create_user_form()


@users.i18n_route("/users/<int:user_id>")
@require_permission("auth_db.view.all")
@injector.inject
def view_user(user_id, duc: DatabaseUserController = None):
    return duc.view_user_page(user_id)


@users.i18n_route("/users/<int:user_id>/edit", methods=['GET', 'POST'])
@require_permission("auth_db.edit")
@injector.inject
def edit_user(user_id, duc: DatabaseUserController = None):
    return duc.edit_user_form(user_id)


@users.i18n_route("/users/<int:user_id>/reset", methods=['GET', 'POST'])
@require_permission("auth_db.reset")
@injector.inject
def reset_password(user_id, duc: DatabaseUserController = None):
    return duc.reset_password_form(user_id)
