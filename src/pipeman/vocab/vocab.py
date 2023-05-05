import flask
from autoinject import injector
from pipeman.db import Database
import pipeman.db.orm as orm
from pipeman.i18n import MultiLanguageString, gettext
from pipeman.db import BaseObjectRegistry
import json
import csv


@injector.injectable_global
class VocabularyRegistry(BaseObjectRegistry):

    def __init__(self):
        super().__init__("vocabulary")

    def list_vocabularies(self):
        for vocab_name in self.sorted_keys():
            yield vocab_name, self[vocab_name]["display"], self[vocab_name]["uri"]

    def display_name(self, vocab_name):
        return MultiLanguageString(self[vocab_name]["display"])

    def register(self, obj_name, *args, terms=None, **kwargs):
        super().register(obj_name, *args, **kwargs)
        if terms:
            self.register_terms_from_dict(obj_name, terms)

    @injector.inject
    def register_terms_from_dict(self, vocab_name, terms: dict, vtc: "pipeman.vocab.vocab.VocabularyTermController" = None):
        vtc.save_terms_from_dict(vocab_name, terms)

    @injector.inject
    def register_terms_from_csv(self, vocab_name, term_file, vtc: "pipeman.vocab.vocab.VocabularyTermController" = None):
        with open(term_file, "r", encoding="utf-8") as h:
            r = csv.reader(h)
            header = None
            for line in r:
                if header is None:
                    header = line
                    continue
                vtc.upsert_term_by_map(vocab_name, line, header)


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
            title=gettext("pipeman.vocab.page.list_vocabularies.title")
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
                self.upsert_term(
                    vocab_name,
                    tsname,
                    terms[tsname]["display"] if "display" in terms[tsname] else {},
                    terms[tsname]["description"] if "description" in terms[tsname] else {},
                    session
                )

    def upsert_term_by_map(self, vocab_name, line, header):
        displays = {}
        descriptions = {}
        tsname = ""
        for idx, key in enumerate(header):
            if key == "short_name":
                tsname = line[idx]
            elif key.startswith("display__"):
                displays[key[9:]] = line[idx]
            elif key.startswith("description__"):
                displays[key[13:]] = line[idx]
            else:
                raise ValueError(f"Unrecognized column header {key}")
        if not tsname:
            if not displays:
                raise ValueError(f"Missing a term name")
            key_name = "und" if "und" in displays else "en"
            if key_name not in displays:
                raise ValueError(f"Missing a fallback term name")
            tsname = displays[key_name].replace(" ", "_").lower()
        with self.db as session:
            self.upsert_term(vocab_name, tsname, displays, descriptions, session)

    def get_term_id(self, vocab_name, tsname):
        with self.db as session:
            term = session.query(orm.VocabularyTerm).filter_by(vocabulary_name=vocab_name, short_name=tsname).first()
            if term:
                return term.id
            return None

    def upsert_term(self, vocab_name, tsname, display, description, session):
        term = session.query(orm.VocabularyTerm).filter_by(vocabulary_name=vocab_name, short_name=tsname).first()
        if not term:
            t = orm.VocabularyTerm(
                vocabulary_name=vocab_name,
                short_name=tsname,
                display_names=json.dumps(display),
                descriptions=json.dumps(description)
            )
            session.add(t)
        else:
            dn = json.loads(term.display_names)
            desc = json.loads(term.descriptions)
            if display:
                dn.update(display)
            if description:
                desc.update(description)
            term.display_names = json.dumps(dn)
            term.descriptions = json.dumps(desc)
        session.commit()
