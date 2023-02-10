import flask

dfo = flask.Blueprint("dfo", __name__)


@dfo.route("/tos")
def tos():
    return "tos"


@dfo.route("/privacy")
def privacy():
    return "privacy"
