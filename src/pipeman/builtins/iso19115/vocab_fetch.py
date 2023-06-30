import requests
import csv
from pipeman.vocab import VocabularyTermController
from autoinject import injector
import xml.etree.ElementTree as ET
import zrlog


@injector.injectable
class ISO19115VocabularyManager:

    vtc: VocabularyTermController = None

    @injector.construct
    def __init__(self):
        self.log = zrlog.get_logger("pipeman.iso19115")

    def fetch(self):
        self.fetch_link_properties()
        self.fetch_schema_terms()

    def fetch_schema_terms(self):
        self.log.info(f"Loading ISO-19115 schema terms")
        link = 'https://standards.iso.org/iso/19115/resources/Codelists/cat/codelists.xml'
        resp = requests.get(link)
        tree = ET.fromstring(resp.text)
        for codelist in tree.findall('{http://standards.iso.org/iso/19115/-3/cat/1.0}codelistItem'):
            actual_codelist = codelist[0]
            iso_name = actual_codelist.attrib.get("id")
            vocab_name = f"iso19115_{iso_name[0:5].lower()}"
            to_split = iso_name[5:]
            for c in to_split:
                if c.isupper():
                    vocab_name += "_"
                vocab_name += c.lower()
            vocab_terms = {}
            for entry in actual_codelist.findall("{http://standards.iso.org/iso/19115/-3/cat/1.0}codeEntry"):
                name = entry[0].find("{http://standards.iso.org/iso/19115/-3/cat/1.0}name")[0].text.strip()
                desc = entry[0].find("{http://standards.iso.org/iso/19115/-3/cat/1.0}description")[0].text.strip()
                vocab_terms[name] = {
                    "display": {
                        "und": name,
                    },
                    "description": {
                        "en": desc,
                    }
                }
            self.log.debug(f"{len(vocab_terms)} loaded for {vocab_name}")
            self.vtc.save_terms_from_dict(vocab_name, vocab_terms)

    def fetch_link_properties(self):
        link = 'https://raw.githubusercontent.com/OSGeo/Cat-Interop/master/LinkPropertyLookupTable.csv'
        resp = requests.get(link)
        dict = {}
        for row in csv.reader(resp.text.split("\n")):
            if len(row) < 2:
                continue
            if row[0] == "identifier":
                continue
            dict[row[0]] = {
                "display": {
                    "en": row[2]
                },
                "description": {
                    "en": row[8]
                }
            }
        self.vtc.save_terms_from_dict("iso19115_link_protocols", dict)
