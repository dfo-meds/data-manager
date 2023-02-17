import flask

# Just for registering the templates folder
erddap = flask.Blueprint("erddap", __name__, template_folder="templates")
