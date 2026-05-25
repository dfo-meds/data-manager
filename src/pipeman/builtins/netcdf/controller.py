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
import pathlib
import logging
import uuid
import zrlog
import typing as t


@injector.injectable
class NetCDFController:

    dc: DatasetController = None

    @injector.construct
    def __init__(self):
        self.log = zrlog.get_logger("pipeman.netcdf")

    def populate_from_netcdf(self, dataset_id: t.Optional[int] = None):
        form = NetCDFTemplateForm(self.dc, dataset_id)
        if form.validate_on_submit():
            if self._populate_from_file(form.dataset_id.data, form.netcdf_file.data):
                flasht("pipeman.netcdf.page.populate_from_netcdf.success", "success")
                return flask.redirect(
                    flask.url_for("core.view_dataset", dataset_id=form.dataset_id.data)
                )
            else:
                flasht("pipeman.netcdf.page.populate_from_netcdf.error", "error")
        return flask.render_template(
            "form.html",
            form=form,
            title=gettext("pipeman.netcdf.page.populate_from_netcdf.title"),
            instructions=gettext("pipeman.netcdf.page.populate_from_netcdf.instructions")
        )

    def _populate_from_file(self, dataset_id, file_data):
        dataset = self.dc.load_dataset(dataset_id)
        try:
            with tempfile.TemporaryDirectory() as td:
                td = pathlib.Path(td)
                tf = td / str(uuid.uuid4())
                with open(tf, "wb") as h:
                    file_data.save(h)
                self.log.info(f"Setting metadata for {dataset_id} from uploaded file {file_data.filename}")
                if file_data.filename.endswith(".nc"):
                    return self._populate_from_netcdf(dataset, tf)
                elif file_data.filename.endswith(".cdl"):
                    return self._populate_from_cdl(dataset, tf)
                elif file_data.filename.endswith(".xml") or file_data.filename.endswith(".ncml"):
                    return self._populate_from_ncml(dataset, tf)
                else:
                    raise ValueError(f"Unrecognized file extension for {file_data.filename}")
        except Exception as ex:
            self.log.exception(f"Error processing uploaded file")
            return False

    def _populate_from_cdl(self, dataset, cdl_file: pathlib.Path):
        # TODO
        raise NotImplementedError()

    def _populate_from_ncml(self, dataset, ncml_file: pathlib.Path):
        # TODO
        raise NotImplementedError()

    def _populate_from_netcdf(self, dataset, netcdf_file: pathlib.Path):
        nf = None
        result = True
        try:
            nf = nc.Dataset(str(netcdf_file), "r")
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
            results = dataset.set_from_file_metadata("netcdf", {
                "global": metadata,
                "variables": variables,
                "dimensions": dimensions
            })
            # TODO: handle errors in results
            self.dc.save_metadata(dataset)
        except Exception as ex:
            self.log.exception(f"Error processing NetCDF file")
            result = False
        finally:
            if nf:
                nf.close()
        return result


class NetCDFTemplateForm(PipemanFlaskForm):

    dataset_id = wtf.SelectField(
        DelayedTranslationString("pipeman.netcdf.page.populate_from_netcdf.dataset"),
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
        DelayedTranslationString("pipeman.netcdf.page.populate_from_netcdf.netcdf_file"),
        validators=[
            fwtff.FileAllowed(['nc', 'cdl', 'xml', 'ncml']),
            fwtff.FileRequired()
        ]
    )

    submit = wtf.SubmitField(
        DelayedTranslationString("pipeman.common.submit")
    )

    def __init__(self, dc: DatasetController, dataset_id = None):
        dataset_id = int(dataset_id)
        options = dc.list_datasets_for_component()
        kwargs = {}
        if dataset_id and any(dataset_id == x[0] for x in options):
            kwargs["dataset_id"] = dataset_id
        super().__init__(**kwargs)
        self.dataset_id.choices = options

