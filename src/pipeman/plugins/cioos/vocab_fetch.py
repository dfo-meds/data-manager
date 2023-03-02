import requests
import csv
from pipeman.vocab import VocabularyTermController
from autoinject import injector
import xml.etree.ElementTree as ET
import zirconium as zr


@injector.injectable
class CIOOSVocabularyManager:

    cfg: zr.ApplicationConfig = None
    vtc: VocabularyTermController = None

    @injector.construct
    def __init__(self):
        self.cioos_eovs_list_url = self.cfg.as_str(
            ("pipeman", "cioos", "eov_list_url"),
            default="https://raw.githubusercontent.com/cioos-siooc/metadata-entry-form/main/src/eovs.json"
        )

    def fetch(self):
        self.fetch_eovs()

    def fetch_eovs(self):
        resp = requests.get(self.cioos_eovs_list_url)
        self.vtc.clear_terms_from_dict("cioos_eovs")
        cioos_eovs = resp.json()
        if "eovs" in cioos_eovs:
            eov_terms = {}
            for eov in cioos_eovs["eovs"]:
                eov_terms[eov['value']] = {
                    'display': {
                        'en': eov['label EN'],
                        'fr': eov['label FR']
                    },
                    'description': {
                        'en': eov['definition EN'],
                        'fr': eov['definition FR']
                    }
                }
            self.vtc.save_terms_from_dict("cioos_eovs", eov_terms)
        else:
            print("no eovs variable found")
