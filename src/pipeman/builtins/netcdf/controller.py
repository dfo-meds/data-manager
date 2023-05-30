from autoinject import injector
from pipeman.dataset import DatasetController
from pipeman.util.flask import PipemanFlaskForm, flasht, Select2Widget
from pipeman.i18n import gettext, DelayedTranslationString
import flask
import wtforms as wtf
import wtforms.validators as wtfv
import flask_wtf.file as fwtff
import netCDF4 as nc
import tempfile
import os


@injector.injectable
class NetCDFController:

    dc: DatasetController = None

    @injector.construct
    def __init__(self):
        pass

    def populate_from_netcdf(self):
        form = NetCDFTemplateForm(self.dc)
        if form.validate_on_submit():
            if self._populate_from_netcdf(form.dataset_id.data, form.netcdf_file.data):
                flasht("pipeman.from_netcdf.page.populate_from_netcdf.success", "success")
            else:
                flasht("pipeman.from_netcdf.page.populate_from_netcdf.error", "error")
        return flask.render_template(
            "form.html",
            form=form,
            title=gettext("pipeman.from_netcdf.page.populate_from_netcdf.title"),
            instructions=gettext("pipeman.from_netcdf.page.populate_from_netcdf.instructions")
        )

    def _populate_from_netcdf(self, dataset_id, netcdf_file):
        dataset = self.dc.load_dataset(dataset_id)
        tf = None
        nf = None
        result = True
        try:
            tf = tempfile.mktemp()
            with open(tf, "wb") as h:
                netcdf_file.save(h)
            nf = nc.Dataset(tf, "r")
            metadata = {
                key: nf.getncattr(key)
                for key in nf.ncattrs()
            }
            dimensions = [dname for dname in nf.dimensions]
            variables = {}
            for vname in nf.variables:
                variables[vname] = {
                    key: nf.variables[vname].getncattr(key)
                    for key in nf.variables[vname].ncattrs()
                }
                variables[vname]["_dimensions"] = [x.name for x in nf.variables[vname].get_dims()]
                if nf.variables[vname].datatype == str:
                    variables[vname]["_data_type"] = 'str'
                else:
                    variables[vname]["_data_type"] = nf.variables[vname].datatype
            dataset.set_from_file_metadata("netcdf", {
                "global": metadata,
                "variables": variables,
                "dimensions": dimensions
            })
            self.dc.save_dataset(dataset)
        finally:
            if nf:
                nf.close()
            os.unlink(tf)
        return result


class NetCDFTemplateForm(PipemanFlaskForm):

    dataset_id = wtf.SelectField(
        DelayedTranslationString("pipeman.from_netcdf.page.populate_from_netcdf.dataset"),
        choices=[],
        coerce=int,
        widget=Select2Widget(placeholder=DelayedTranslationString("pipeman.common.placeholder")),
        validators=[
            wtfv.InputRequired(
                message=DelayedTranslationString("pipeman.error.required_field")
            )
        ]
    )

    netcdf_file = fwtff.FileField(
        DelayedTranslationString("pipeman.from_netcdf.page.populate_from_netcdf.netcdf_file"),
        validators=[
            fwtff.FileAllowed(["nc"]),
            fwtff.FileRequired()
        ]
    )

    submit = wtf.SubmitField(
        DelayedTranslationString("pipeman.common.submit")
    )

    def __init__(self, dc: DatasetController):
        super().__init__()
        self.dataset_id.choices = dc.list_datasets_for_component()


