from autoinject import injector
from pipeman.db import Database
import pipeman.db.orm as orm
import json


@injector.injectable_global
class VocabularyRegistry:

    def __init__(self):
        self._vocabularies = {}

    def register_vocabulary(self, name, display, uri=None):
        if name in self._vocabularies:
            self._vocabularies[name][0].update(display)
            if uri is not None:
                self._vocabularies[name][1] = uri
        else:
            self._vocabularies[name] = (display, uri)

    def register_from_dict(self, d: dict):
        if d:
            for key in d:
                self.register_vocabulary(key, d[key]["display"], d[key]["uri"])
                if "terms" in d[key]:
                    self.register_terms_from_dict(key, d[key]["terms"])

    @injector.inject
    def register_terms_from_dict(self, vocab_name, terms: dict, vtc: "pipeman.vocab.vocab.VocabularyTermController"):
        vtc.save_terms_from_dict(vocab_name, terms)


@injector.injectable
class VocabularyTermController:

    reg: VocabularyRegistry = None
    db: Database = None

    @injector.construct
    def __init__(self):
        pass

    def save_terms_from_dict(self, vocab_name, terms: dict):
        with self.db as session:
            for tsname in terms:
                term = session.query(orm.VocabularyTerm).filter_by(vocabulary_name=vocab_name, short_name=tsname).first()
                if not term:
                    t = orm.VocabularyTerm(
                        vocabulary_name=vocab_name,
                        short_name=tsname,
                        display_names=json.dumps(terms[tsname]["display"] if "display" in terms[tsname] else {}),
                        descriptions=json.dumps(terms[tsname]["description"] if "description" in terms[tsname] else {})
                    )
                    session.add(t)
                else:
                    dn = json.loads(term.display_names)
                    desc = json.loads(term.descriptions)
                    if "display" in terms[tsname]:
                        dn.update(terms[tsname]["display"])
                        if "description" in terms[tsname]:
                            desc.update(terms[tsname]["description"])
                    else:
                        dn.update(terms[tsname])
                    term.display_names = json.dumps(dn)
                    term.descriptions = json.dumps(desc)
            session.commit()
