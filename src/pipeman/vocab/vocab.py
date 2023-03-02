import flask
from autoinject import injector
from pipeman.db import Database
import pipeman.db.orm as orm
from pipeman.i18n import MultiLanguageString, gettext
import json


@injector.injectable_global
class VocabularyRegistry:

    def __init__(self):
        self._vocabularies = {}

    def list_vocabularies(self):
        names = list(self._vocabularies.keys())
        names.sort()
        for vocab_name in names:
            yield vocab_name, self._vocabularies[vocab_name][0], self._vocabularies[vocab_name][1]

    def display_name(self, vocab_name):
        return MultiLanguageString(self._vocabularies[vocab_name][0])

    def register_vocabulary(self, name, display, uri=None):
        if name in self._vocabularies:
            self._vocabularies[name][0].update(display)
            if uri is not None:
                self._vocabularies[name][1] = uri
        else:
            self._vocabularies[name] = (display, uri)

    def vocabulary_exists(self, name):
        return name in self._vocabularies

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

    def list_vocabularies_page(self):
        return flask.render_template(
            "list_vocabularies.html",
            vocabularies=self._vocabulary_iterator(),
            title=gettext("pipeman.vocabularies_list.title")
        )

    def _vocabulary_iterator(self):
        for name, display, uri in self.reg.list_vocabularies():
            d = display.copy()
            d["und"] = name
            link = flask.url_for("core.vocabulary_term_list", vocab_name=name)
            yield name, MultiLanguageString(d), uri, link

    def list_terms_page(self, vocabulary_name):
        return flask.render_template(
            "list_terms.html",
            terms=self._term_iterator(vocabulary_name),
            title=self.reg.display_name(vocabulary_name)
        )

    def _term_iterator(self, vocabulary_name):
        with self.db as session:
            for term in session.query(orm.VocabularyTerm).filter_by(vocabulary_name=vocabulary_name):
                display_names = json.loads(term.display_names) if term.display_names else {}
                descriptions = json.loads(term.descriptions) if term.descriptions else {}
                display_names["und"] = term.short_name
                descriptions["und"] = ""
                yield term.short_name, MultiLanguageString(display_names), MultiLanguageString(descriptions)

    def clear_terms_from_dict(self, vocab_name):
        with self.db as session:
            session.query(orm.VocabularyTerm).filter_by(vocabulary_name=vocab_name).delete()
            session.commit()

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
