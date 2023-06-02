from autoinject import injector
import uuid
from pipeman.workflow import ItemResult
from pipeman.db import Database
import pipeman.db.orm as orm
import json
import hashlib
import zrlog
import sqlalchemy as sa
import zirconium as zr
from pipeman.util.errors import RecoverableError, UnrecoverableError, TranslationNotAvailableYet
from pipeman.dataset import DatasetController
from pipeman.entity import EntityController
import datetime


@injector.injectable
class TranslationEngine:

    db: Database = None
    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self, send_immediately: bool = True):
        self._log = zrlog.get_logger("pipeman.i18n.workflow")
        self._send_translations_immediately = send_immediately

    def cleanup_requests(self):
        self._log.notice(f"Cleaning up old requests")
        success_retention_days = self.config.as_int(("pipeman", "translation", "success_retention_days"), default=7)
        failure_retention_days = self.config.as_int(("pipeman", "translation", "failure_retention_days"), default=31)
        with self.db as session:
            q = (
                sa.delete(orm.TranslationRequest)
                .where(orm.TranslationRequest.allow_reuse == False)
                .where(orm.TranslationRequest.state == orm.TranslationState.SUCCESS)
                .where(orm.TranslationRequest.created_date < (datetime.datetime.now() - datetime.timedelta(days=success_retention_days)))
            )
            session.execute(q)
            q = (
                sa.delete(orm.TranslationRequest)
                .where(orm.TranslationRequest.state == orm.TranslationState.FAILURE)
                .where(orm.TranslationRequest.created_date < (datetime.datetime.now() - datetime.timedelta(days=failure_retention_days)))
            )
            session.execute(q)
            session.commit()

    def _find_request(self, key, lang, original_text):
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
                if self._send_translations_immediately:
                    self._do_translation(trans_req, session)
            return trans_req

    def _stable_hash(self, source_info: dict):
        h = hashlib.sha256()
        keys = list(source_info.keys())
        keys.sort()
        for key in keys:
            h.update(f"{key}::{source_info[key]}".encode("utf-8"))
        return h.hexdigest()

    def fetch_translation(self, key, lang, original_text) -> str:
        trans_req = self._find_request(key, lang, original_text)
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


@injector.inject
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
        return ItemResult.BATCH_DELAY
    else:
        # All done!
        context["_has_completed"] = True
        return ItemResult.SUCCESS


def set_translation(step, context):
    remove_in_translation_flag(step, context)


def remove_in_translation_flag(step, context):
    if context['object_type'] == 'dataset' and context['type'] == 'field':
        _update_dataset_field_translation(
            context['object_id'],
            context['field_name'],
            context['index'],
            context['text_values'] if '_has_completed' in context and context['_has_completed'] else None
        )
    else:
        _update_entity_field_translation(
            context['object_type'],
            context['object_id'],
            context['field_name'],
            context['index'],
            context['text_values'] if '_has_completed' in context and context['_has_completed'] else None
        )


@injector.inject
def _update_entity_field_translation(entity_type, entity_id, field_name, index, translation, ec: EntityController):
    entity = ec.load_entity(entity_type, entity_id)
    _set_field_translation(entity, field_name, index, translation)
    ec.save_entity(entity)


@injector.inject
def _update_dataset_field_translation(dataset_id, field_name, index, translation, dc: DatasetController):
    dataset = dc.load_dataset(dataset_id)
    _set_field_translation(dataset, field_name, index, translation)
    dc.save_metadata(dataset)


def _set_field_translation(field_container, field_name, index, translation):
    field = field_container.get_field(field_name)
    if field is None:
        raise ValueError(f"No such field: {field_name}")
    field.set_from_translation(translation, index)
