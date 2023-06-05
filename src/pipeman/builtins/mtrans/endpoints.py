from pipeman.util.flask import MultiLanguageBlueprint, PipemanFlaskForm, flasht
from pipeman.i18n.workflow import TranslationEngine
from pipeman.auth import require_permission
from .mtrans import ManualTranslationEngine, ManualTranslationEntry
from autoinject import injector
import flask
import csv
import io
import datetime
import wtforms as wtf
from flask_wtf.file import FileField, FileAllowed, FileRequired
from pipeman.util.errors import TranslatableError
from pipeman.i18n import gettext
import logging
import tempfile
import pathlib


mtrans = MultiLanguageBlueprint("mtrans", __name__)


@mtrans.route("/translations/download")
@require_permission("translations.manage")
@injector.inject
def download_translations(te: TranslationEngine = None):
    if not isinstance(te, ManualTranslationEngine):
        return flask.abort(404)
    content = io.StringIO()
    writer = csv.writer(content)
    writer.writerow(["GUID",
                     "Original Text",
                     "Original Language",
                     "Translated Language",
                     "Translation"])
    for mte in te.export_translations():
        writer.writerow([mte.guid,
                         mte.source_text,
                         mte.source_language,
                         mte.target_language,
                         ""])
    bytes_buff = io.BytesIO(content.getvalue().encode("utf-8"))
    return flask.send_file(bytes_buff,
                           "text/csv",
                           as_attachment=True,
                           download_name=f"translations_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv")


@mtrans.route("/translations/upload", methods=['GET', 'POST'])
@require_permission("translations.manage")
@injector.inject
def upload_translations(te: TranslationEngine = None):
    if not isinstance(te, ManualTranslationEngine):
        return flask.abort(404)
    form = TranslationUploadForm()
    if form.validate_on_submit():
        with tempfile.TemporaryDirectory() as td:
            tmp_file = pathlib.Path(td) / "temp_data.csv"
            form.file_upload.data.save(tmp_file)
            with open(tmp_file, "r") as h:
                reader = csv.reader(h)
                header = None
                req_size = 0
                for idx, line in enumerate(reader):
                    if header is None:
                        header = [x.lower() for x in line]
                        if "guid" not in header:
                            flasht("pipeman.mtrans.error.no_guid_column", "error")
                            break
                        elif "translation" not in header:
                            flasht("pipeman.mtrans.error.no_translation_column", "error")
                            break
                        header = [
                            header.index("guid"),
                            header.index("translation")
                        ]
                        req_size = max(header)
                        continue
                    elif not line:
                        continue
                    elif len(line) < req_size:
                        flasht("pipeman.mtrans.error.not_enough_columns", "warning", lineno=idx)
                        continue
                    elif not line[header[0]]:
                        flasht("pipeman.mtrans.error.missing_guid", "warning", lineno=idx)
                        continue
                    elif not line[header[1]]:
                        flasht("pipeman.mtrans.error.missing_translation", "warning", lineno=idx, guid=line[header[0]])
                        continue
                    else:
                        try:
                            te.import_translation(ManualTranslationEntry(
                                guid=line[header[0]],
                                translation=line[header[1]]
                            ))
                        except TranslatableError as ex:
                            flasht("pipeman.mtrans.error.line_processing_error", "warning", lineno=idx, original=str(ex))
                            logging.getLogger("pipeman.mtrans").warning(str(ex))
                        except Exception as ex:
                            flasht("pipeman.mtrans.error.other_error", "error", lineno=idx)
                            logging.getLogger("pipeman.mtrans").exception(f"Error while processing updated translation file")
                else:
                    flasht("pipeman.mtrans.page.upload_translations.success", "success")
        form.file_upload.data = None
    return flask.render_template(
        "form.html",
        form=form,
        title=gettext("pipeman.mtrans.page.upload.title"),
        instructions=gettext("pipeman.mtrans.page.upload.instructions")
    )


class TranslationUploadForm(PipemanFlaskForm):

    file_upload = FileField(
        gettext("pipeman.label.translation.upload"),
        validators=[
            FileAllowed(["csv"]),
            FileRequired()
        ]
    )

    submit = wtf.SubmitField(
        gettext("pipeman.common.submit")
    )
