import pipeman.db.orm as orm
from pipeman.i18n.workflow import TranslationEngine
import json
from pipeman.util.errors import TranslatableError


class ManualTranslationEntry:

    def __init__(self,
                 guid: str,
                 source_text: str = None,
                 source_language: str = None,
                 target_language: str = None,
                 translation: str = None):
        self.guid = guid
        self.source_text = source_text
        self.source_language = source_language
        self.target_language = target_language
        self.translation = translation
        if not self.guid:
            raise TranslatableError("pipeman.mtrans.error.missing_guid")


class ManualTranslationEngine(TranslationEngine):

    def export_translations(self):
        found_source_hashes = set()
        with self.db as session:
            for tr in session.query(orm.TranslationRequest).filter_by(
                state=orm.TranslationState.DELAYED
            ):
                if tr.source_hash in found_source_hashes:
                    continue
                src_info = json.loads(tr.source_info)
                source_key = 'en' if 'en' in src_info else list(k for k in src_info.keys() if k != 'und')[0]
                yield ManualTranslationEntry(
                    tr.guid,
                    src_info[source_key],
                    source_key,
                    tr.lang_key,
                    ""
                )
                found_source_hashes.add(f"{tr.source_hash}::{tr.lang_key}")

    def import_translation(self, translation: ManualTranslationEntry):
        with self.db as session:
            if not translation.translation:
                raise TranslatableError("pipeman.mtrans.error.no_translation", guid=translation.guid)
            tr = session.query(orm.TranslationRequest).filter_by(guid=translation.guid).first()
            if not tr:
                raise TranslatableError("pipeman.mtrans.error.no_such_request", guio=translation.guid)
            if not tr.state == orm.TranslationState.DELAYED:
                raise TranslatableError("pipeman.mtrans.error.request_already_completed", guid=translation.guid)
            tr.set_translation(translation.translation, True)
            session.commit()
            for tr2 in session.query(orm.TranslationRequest).filter_by(
                source_hash=tr.source_hash,
                lang_key=tr.lang_key,
                state=orm.TranslationState.DELAYED
            ):
                tr2.set_translation(translation.translation, False)
                session.commit()

    def do_translation(self, tr: orm.TranslationRequest, session, info: dict):
        tr.delay()
        session.commit()
