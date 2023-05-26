from pipeman.util.flask import MultiLanguageBlueprint, PipemanFlaskForm
from pipeman.i18n.workflow import TranslationEngine
from pipeman.auth import require_permission
from .mtrans import ManualTranslationEngine
from autoinject import injector
import flask
import csv
import io
import datetime
import wtforms as wtf
from pipeman.i18n import gettext


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
                           download_name=f"translations_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}")


@mtrans.route("/translations/upload", methods=['GET', 'POST'])
@require_permission("translations.manage")
@injector.inject
def upload_translations(te: TranslationEngine = None):
    if not isinstance(te, ManualTranslationEngine):
        return flask.abort(404)
    form = TranslationUploadForm()
    if form.validate_on_submit():
        # do stuff
        pass
    return flask.render_template(
        "form.html",
        form=form,
        title=gettext("pipeman.mtrans.page.upload.title"),
        instructions=gettext("pipeman.mtrans.page.upload.instructions")
    )


class TranslationUploadForm(PipemanFlaskForm):

    file_upload = wtf.FileField(
        gettext("pipeman.label.translation.upload")
    )

    submit = wtf.SubmitField(
        gettext("pipeman.common.submit")
    )
