import requests
from pipeman.vocab import VocabularyTermController
from autoinject import injector
import xml.etree.ElementTree as ET
import logging
import bs4


@injector.injectable
class CFVocabularyManager:

    vtc: VocabularyTermController = None

    @injector.construct
    def __init__(self):
        self.log = logging.getLogger("pipeman.cf")

    def fetch(self):
        self.fetch_cf_standard_names()
        self.fetch_ud_prefixes()
        self.fetch_ud_units()

    def fetch_cf_standard_names(self):
        self.log.out(f"Loading CF standard names")
        # TODO convert to http://cfconventions.org/Data/cf-standard-names/current/src/cf-standard-name-table.xml
        terms = {}
        link = "http://cfconventions.org/Data/cf-standard-names/current/build/cf-standard-name-table.html"
        resp = requests.get(link)
        soup = bs4.BeautifulSoup(resp.text, 'html.parser')
        sn_table = soup.find('table', id="standard_name_table")
        for sn_tr in sn_table.find_all("tr"):
            base = sn_tr.find("td")
            var_name = base.find("code").find("a").text
            var_desc = sn_tr.find("div").text
            terms[var_name] = {
                "display": {
                    "en": var_name,
                },
                "description": {
                    "en": var_desc,
                }
            }
        self.log.info(f"Found {len(terms)} standard names")
        self.vtc.save_terms_from_dict("cf_standard_names", terms)

    def fetch_ud_prefixes(self):
        self.log.out("Loading UDUnit prefixes")
        terms = {}
        links = [
            "https://docs.unidata.ucar.edu/udunits/current/udunits2-prefixes.xml",
        ]
        for link in links:
            resp = requests.get(link)
            tree = ET.fromstring(resp.text)
            for prefix in tree.findall("prefix"):
                name = prefix.find("name").text
                value = prefix.find("value").text
                symbol = prefix.find("symbol").text
                if not symbol:
                    print(prefix)
                terms[symbol] = {
                    "display": {
                        "und": name,
                    },
                    "description": {
                        "en": f"Multiplied by {value}",
                        "fr": f"Multiplié par {value}"
                    }
                }
        self.log.info(f"Found {len(terms)} udunit prefixes")
        self.vtc.save_terms_from_dict("udunit_prefixes", terms)

    def fetch_ud_units(self):
        self.log.out(f"Loading UDUnit units")
        links = [
            "https://docs.unidata.ucar.edu/udunits/current/udunits2-base.xml",
            "https://docs.unidata.ucar.edu/udunits/current/udunits2-derived.xml",
            "https://docs.unidata.ucar.edu/udunits/current/udunits2-derived.xml",
            "https://docs.unidata.ucar.edu/udunits/current/udunits2-accepted.xml",
        ]
        terms = {}
        for link in links:
            resp = requests.get(link)
            tree = ET.fromstring(resp.text)
            for unit in tree.findall("unit"):
                n = unit.find("name")
                if n is None:
                    n = unit.find("aliases").find("name")
                name = n.find("singular").text
                desc = unit.find("definition").text
                sym = unit.find("symbol")
                if sym is None:
                    sym = unit.find("aliases").find("symbol")
                symbol = sym.text if sym is not None else name
                if symbol in terms and terms[symbol]["description"]["en"] != desc:
                    logging.getLogger("pipeman.cf").warning(f"Duplicate unit name detected: {symbol}")
                    continue

                terms[symbol] = {
                    "display": {
                        "en": name,
                    },
                    "description": {
                        "en": desc,
                    }
                }
        self.log.info(f"Found {len(terms)} udunit units")
        self.vtc.save_terms_from_dict("udunit_units", terms)



