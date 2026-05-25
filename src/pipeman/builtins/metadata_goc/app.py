import flask

# Just for registering the templates folder
iso19139nap = flask.Blueprint("iso19139nap", __name__, template_folder="templates")
