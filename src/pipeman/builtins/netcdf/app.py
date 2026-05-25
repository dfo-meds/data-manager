import flask
from pipeman.util.flask import MultiLanguageBlueprint
from autoinject import injector
from .controller import NetCDFController

# Just for registering the templates folder
netcdf = MultiLanguageBlueprint("netcdf", __name__, template_folder="templates")


@netcdf.i18n_route("/from-netcdf", methods=["GET", "POST"])
@injector.inject
def populate_from_netcdf(ncc: NetCDFController = None):
    return ncc.populate_from_netcdf()


@netcdf.i18n_route("/from-netcdf/<dataset_id>", methods=["GET", "POST"])
@injector.inject
def populate_from_netcdf_dsid(dataset_id, ncc: NetCDFController = None):
    return ncc.populate_from_netcdf(dataset_id)
