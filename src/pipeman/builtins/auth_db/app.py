import flask
from flask_login import login_required
from pipeman.auth import require_permission
from .controller import DatabaseUserController
from autoinject import injector

users = flask.Blueprint("users", __name__)


@users.route("/me")
@login_required
@injector.inject
def view_myself(duc: DatabaseUserController = None):
    return duc.view_myself_page()


@users.route("/me/edit", methods=['GET', 'POST'])
@login_required
@injector.inject
def edit_myself(duc: DatabaseUserController = None):
    return duc.edit_myself_form()


@users.route("/me/change-password", methods=['GET', 'POST'])
@login_required
@injector.inject
def change_my_password(duc: DatabaseUserController = None):
    return duc.change_password_form()


@users.route("/users")
@require_permission("auth_db.view_users")
@injector.inject
def list_users(duc: DatabaseUserController = None):
    return duc.list_users_page()


@users.route("/users/create", methods=['GET', 'POST'])
@require_permission("auth_db.create_users")
@injector.inject
def create_user(duc: DatabaseUserController = None):
    return duc.create_user_form()


@users.route("/users/<username>")
@require_permission("auth_db.view_users")
@injector.inject
def view_user(username, duc: DatabaseUserController = None):
    return duc.view_user_page(username)


@users.route("/users/<username>/edit", methods=['GET', 'POST'])
@require_permission("auth_db.edit_users")
@injector.inject
def edit_user(username, duc: DatabaseUserController = None):
    return duc.edit_user_form(username)


@users.route("/users/<username>/reset", methods=['GET', 'POST'])
@require_permission("auth_db.reset_passwords")
@injector.inject
def reset_password(username, duc: DatabaseUserController = None):
    return duc.reset_password_form(username)
