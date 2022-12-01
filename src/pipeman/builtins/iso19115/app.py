import flask

# Just for registering the templates folder
iso19115 = flask.Blueprint("iso", __name__, template_folder="templates")
