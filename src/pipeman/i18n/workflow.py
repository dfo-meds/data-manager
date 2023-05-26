from autoinject import injector
import uuid
from pipeman.workflow import ItemResult
from pipeman.db import Database
import pipeman.db.orm as orm
import json
import hashlib
import logging
import zirconium as zr
from pipeman.util.errors import RecoverableError, UnrecoverableError, TranslationNotAvailableYet


@injector.injectable
class TranslationEngine:

    db: Database = None
    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self.log = logging.getLogger("pipeman.i18n.workflow")

    def find_request(self, key, lang, original_text):
        with self.db as session:
            trans_req = session.query(orm.TranslationRequest).filter_by(
                guid=key,
                lang_key=lang
            ).first()
            if not trans_req:
                trans_req = orm.TranslationRequest(
                    guid=key,
                    lang_key=lang,
                    source_info=json.dumps(original_text),
                    source_hash=self._stable_hash(original_text)
                )
                session.add(trans_req)
                session.commit()
            return trans_req

    def _stable_hash(self, source_info: dict):
        h = hashlib.sha256()
        keys = list(source_info.keys())
        keys.sort()
        for key in keys:
            h.update(f"{key}::{source_info[key]}")
        return h.hexdigest()

    def fetch_translation(self, key, lang, original_text) -> str:
        trans_req = self.find_request(key, lang, original_text)
        if trans_req.state == orm.TranslationState.FAILURE:
            raise UnrecoverableError(f"Translation request {trans_req.id} failed")
        elif trans_req.state == orm.TranslationState.SUCCESS:
            return trans_req.translation
        else:
            raise TranslationNotAvailableYet()

    def do_translations(self):
        with self.db as session:
            for trans_req in session.query(orm.TranslationRequest).filter_by(
                state=orm.TranslationState.IN_PROGRESS
            ):
                self._do_translation(trans_req, session)

    def _do_translation(self, tr: orm.TranslationRequest, session):
        # Handle caching here automatically so we don't need to worry about it
        check = session.query(orm.TranslationRequest).filter_by(
            source_hash=tr.source_hash,
            lang_key=tr.lang_key,
            allow_reuse=True,
            state=orm.TranslationState.SUCCESS
        ).first()
        if check:
            tr.set_translation(check.translation, False)
            session.commit()
        else:
            try:
                info = json.loads(tr.handler_info) if tr.handler_info else {}
                res = self.do_translation(tr, session, info)
                if isinstance(res, str):
                    tr.set_translation(res)
                tr.handler_info = json.dumps(info)
                session.commit()
            except RecoverableError as ex:
                self.log.warning(str(ex))
            except Exception as ex:
                self.log.exception(f"Exception while processing translation request {id}")
                tr.mark_failed(str(ex))
                session.commit()

    def do_translation(self, tr: orm.TranslationRequest, session, info: dict):
        raise UnrecoverableError("No translation engine configured")


def fetch_translation(step, context, trans_engine: TranslationEngine = None):
    if "guid" not in context:
        context["guid"] = str(uuid.uuid4())
    originals = {}
    to_translate = []
    for lang in context["text_values"]:
        if lang == '_translation_request':
            continue
        elif lang == 'und' or context['text_values'][lang]:
            originals[lang] = context['text_values'][lang]
        else:
            to_translate.append(lang)
    state = 0
    for lang in to_translate:
        try:
            context["text_values"][lang] = trans_engine.fetch_translation(context["guid"], lang, originals)
        except TranslationNotAvailableYet:
            state = 1
    if state > 0:
        # Still waiting on other items
        return ItemResult.ASYNC_EXECUTE
    else:
        # All done!
        context["_has_completed"] = True
        return ItemResult.SUCCESS


def remove_in_translation_flag(step, context):
    pass


"""


        ctx = {
            'object_type': self.parent_type,
            'object_id': self.parent_id,
            'field_name': self.field_name,
            'text_values': val,
            'type': "field",
            'index': index
        }
"""
