from pipeman.util.flask import MultiLanguageBlueprint
from .controller import NetCDFController
from autoinject import injector

netcdf = MultiLanguageBlueprint("netcdf", __name__)


@netcdf.i18n_route("/from-netcdf", methods=["GET", "POST"])
@injector.inject
def populate_from_netcdf(ncc: NetCDFController = None):
    return ncc.populate_from_netcdf()
