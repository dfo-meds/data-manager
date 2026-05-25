from google.cloud import translate
from google.api_core.exceptions import GoogleAPIError
import pipeman.db.orm as orm
from pipeman.i18n.workflow import TranslationEngine
from pipeman.util.errors import RecoverableError
import json
from html import unescape


class GoogleTranslationEngine(TranslationEngine):

    def __init__(self):
        super().__init__()
        sa_file = self.config.as_str(("pipeman", "translation", "googlecloud", "service_account_file"), default=None)
        self.parent = self.config.as_str(("pipeman", "translation", "googlecloud", "parent"))
        self.allow_reuse = self.config.as_bool(("pipeman", "translation", "googlecloud", "cache_translations"), default=True)
        if sa_file:
            self.translator = translate.TranslationServiceClient.from_service_account_file(
               sa_file
            )
        else:
            self.translator = translate.TranslationServiceClient()

    def do_translation(self, tr: orm.TranslationRequest, session, info: dict):
        source_info = json.loads(tr.source_info)
        try:
            self.log.info(f"Sending translation request {tr.id} to Google Translation")
            if 'en' in source_info:
                response = self.translator.translate_text(
                    parent=self.parent,
                    contents=[source_info['en']],
                    source_language_code='en',
                    target_language_code=tr.lang_key
                )
            else:
                src_key = list(k for k in source_info if k != 'und')[0]
                response = self.translator.translate_text(
                    parent=self.parent,
                    contents=[source_info[src_key]],
                    source_language_code=src_key,
                    target_language_code=tr.lang_key
                )
            if response.translations and response.translations[0].translated_text:
                self.log.debug(f"Translation for {tr.id} set to {response.translations[0].translated_text} by Google Translate")
                tr.set_translation(unescape(response.translations[0].translated_text), self.allow_reuse)
                session.commit()
            else:
                self.log.warning(f"Missing translation in response to {tr.id}: {response}")
        except GoogleAPIError as ex:
            raise RecoverableError("Error calling Google Translate API", ex)
