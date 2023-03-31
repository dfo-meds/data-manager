import flask
from flask_login import login_required
from pipeman.auth import require_permission
from .controller import DatabaseUserController
from autoinject import injector
from pipeman.util.flask import MultiLanguageBlueprint

users = MultiLanguageBlueprint("users", __name__)


@users.i18n_route("/me")
@login_required
@injector.inject
def view_myself(duc: DatabaseUserController = None):
    return duc.view_myself_page()


@users.i18n_route("/me/edit", methods=['GET', 'POST'])
@login_required
@injector.inject
def edit_myself(duc: DatabaseUserController = None):
    return duc.edit_myself_form()


@users.i18n_route("/me/change-password", methods=['GET', 'POST'])
@login_required
@injector.inject
def change_my_password(duc: DatabaseUserController = None):
    return duc.change_password_form()


@users.i18n_route("/users")
@require_permission("auth_db.view_all")
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
