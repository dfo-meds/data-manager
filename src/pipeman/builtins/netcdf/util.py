import requests
from pipeman.vocab import VocabularyTermController
from pipeman.dataset.dataset import Dataset
from pipeman.util import load_object
from pipeman.entity.fields import Field
from pipeman.entity import EntityController
from pipeman.entity.entity import Entity, FieldContainer
from pipeman.i18n import TranslationManager
from autoinject import injector
import zirconium as zr
import xml.etree.ElementTree as ET
import logging
import bs4
import datetime


def preprocess_for_ncml(dataset, **kwargs):
    extras = _preprocess_for_both(dataset, **kwargs)
    return extras


def preprocess_for_cdl(dataset, **kwargs):
    extras = _preprocess_for_both(dataset, **kwargs)
    return extras


def _preprocess_for_both(dataset, **kwargs):
    extras = {
        'global_attributes': _global_attributes(dataset),
        'variables': _variables(dataset)
    }
    keywords = set()
    vocabularies = set()
    for x in dataset.keywords():
        disp = x.to_display("en", use_prefixes=True)
        if disp["primary"]:
            keywords.add(disp["primary"])
        keywords.update(disp["secondary"].values())
        if disp["vocab"]:
            vocabularies.add(disp["vocab"])
    keywords = list(kw.replace(",", "") for kw in keywords)
    keywords.sort()
    extras['basic_keywords'] = ','.join(keywords)
    extras['basic_vocabularies'] = ','.join(vocabularies)
    return extras


def _autodetect_mapping(field: Field):
    dt = field.config("data_type")
    if dt == 'vocabulary':
        return 'vocabulary'
    elif dt == 'key_value':
        return 'key_value'
    elif dt in ('date', 'datetime'):
        return 'datetime'
    elif dt in ('decimal', 'integer', 'float'):
        return 'numeric'
    elif dt in ('text', 'multitext', 'email', 'url', 'telephone'):
        return 'text'
    return None


@injector.inject
def _global_attributes(dataset: Dataset, config: zr.ApplicationConfig = None, **kwargs):
    attrs = _extract_netcdf_attributes(dataset)
    attrs['id'] = dataset.guid()
    attrs['naming_authority'] = config.as_str(("pipeman", "metadata", "naming_authority"), default="pipeman")
    return attrs


@injector.inject
def set_metadata_from_netcdf(dataset: Dataset, file_type: str, metadata: dict, ec: EntityController = None):
    _import_netcdf_attributes(dataset, metadata['global'], 'custom_metadata')
    variables = dataset.get_field('variables')
    current_list = {
        c['source_name']: c for c, _, _ in variables.component_list()
    }
    for var_name in metadata['variables'] or []:
        if var_name not in current_list:
            real_var = ec.reg.new_entity('variable')
            real_var.set_display_name('und', var_name)
            real_var.parent_id = dataset.dataset_id
            real_var.parent_type = 'dataset'
            _import_netcdf_attributes(real_var, metadata['variables'][var_name], 'custom_metadata')
            ec.save_entity(real_var)
            # create a new one
        else:
            real_var = current_list[var_name]
            _import_netcdf_attributes(real_var, metadata['variables'][var_name], 'custom_metadata')
            ec.save_entity(real_var)


def _import_netcdf_attributes(fc: FieldContainer, attributes: dict, extra_field_name: str = None):
    for fn in fc.ordered_field_names():
        field = fc.get_field(fn)
        config = field.config("netcdf", default=None)
        if not config:
            continue
        if 'mapping' not in config or not config['mapping']:
            config['mapping'] = fn
        processor = None
        if 'importer' in config and config['importer']:
            processor = config['importer']
        elif 'processor' in config and config['processor'] and not "." in config['processor']:
            processor = config['processor']
        else:
            processor = _autodetect_mapping(field)
        if processor is not None:
            _import_field_value(processor, config, attributes, fc, field)
    if extra_field_name:
        extras = fc.get_field(extra_field_name)
        values = []
        for attr in attributes:
            val = attributes[str]
            dtype = 'str'
            if isinstance(val, int) or isinstance(val, float):
                dtype = 'numeric'
            elif isinstance(val, list) or isinstance(val, tuple):
                dtype = 'numeric_list'
                val = ','.join(str(x) for x in val)
            values.append({
                'key': attr,
                'value': str(attributes[attr]),
                'data_type': 'dtype'
            })
        extras.set_from_raw(values)


def _import_field_value(processor, *args):
    if processor == 'text':
        _import_text_value(*args)
    elif processor == 'numeric':
        _import_raw_value(*args)
    elif processor == 'vocabulary':
        _import_vocab_value(*args)
    elif processor == 'datetime':
        _import_datetime_value(*args)
    elif processor == 'key_value_pairs':
        pass
    elif processor == 'ref_system':
        _import_ref_system(*args)
    elif processor == 'contact':
        _import_contact(*args)
    elif processor == 'contacts_by_role':
        _import_contacts_by_role(*args)
    else:
        try:
            obj = load_object(processor)
            obj(*args)
        except (AttributeError, ModuleNotFoundError) as ex:
            logging.getLogger("pipeman.netcdf").exception(f"Error loading netcdf field importer: {processor} ")


@injector.inject
def _import_text_value(config: dict, attributes: dict, fc: FieldContainer, field: Field, tm: TranslationManager = None):
    target = config['mapping']
    values = {}
    if target in attributes:
        values['und'] = attributes.pop(target)
    for key in tm.metadata_supported_languages():
        full_key = f"{target}_{key}"
        if full_key in attributes:
            values[key] = attributes.pop(full_key)
    field.set_from_raw(values)


def _import_raw_value(config: dict, attributes: dict, fc: FieldContainer, field: Field):
    target = config["mapping"]
    if target in attributes:
        field.set_from_raw(attributes.pop(target))


def _import_datetime_value(config: dict, attributes: dict, fc: FieldContainer, field: Field):
    target = config["mapping"]
    if target in attributes:
        dt = attributes.pop(target)
        field.set_from_raw(datetime.datetime.fromisoformat(dt) if dt else None)


def _import_ref_system(config: dict, attributes: dict, fc: FieldContainer, field: Field):
    # TODO
    pass


def _import_contact(config: dict, attributes: dict, fc: FieldContainer, field: Field):
    # TODO
    pass


def _import_contacts_by_role(config: dict, attributes: dict, fc: FieldContainer, field: Field):
    # TODO
    pass


@injector.inject
def _import_vocab_value(config: dict, attributes: dict, fc: Field, field: Field, vtc: VocabularyTermController = None):
    target = config["mapping"]
    if target in attributes and attributes[target]:
        term_id = vtc.get_term_id(fc.config('vocabulary_name'), attributes[target].strip())
        if term_id:
            attributes.pop(target)
            field.set_from_raw(term_id)


def _extract_netcdf_attributes(fc: FieldContainer):
    attrs = {}
    for fn in fc.ordered_field_names():
        field = fc.get_field(fn)
        if field.is_empty():
            continue
        config = field.config("netcdf", default=None)
        if not config:
            continue
        target_name = config['mapping'] if 'mapping' in config and config['mapping'] else fn
        processor = config['processor'] if 'processor' in config and config['processor'] else _autodetect_mapping(field)
        _process_field_value(processor, attrs, target_name, field, config, fc)
    return attrs


def _process_field_value(processor: str, *args):
    if processor == 'text':
        _text_processor(*args)
    elif processor == 'vocabulary':
        _vocab_processor(*args)
    elif processor == 'numeric':
        _numeric_processor(*args)
    elif processor == 'datetime':
        _datetime_processor(*args)
    elif processor == 'key_value_pairs':
        _key_value_processor(*args)
    elif processor == 'ref_system':
        _ref_system_processor(*args)
    elif processor == 'contact':
        _contact_processor_initial(*args)
    elif processor == 'contacts_by_role':
        _contact_role_processor(*args)
    elif processor == 'licenses':
        _licenses_processor(*args)
    else:
        try:
            obj = load_object(processor)
            obj(*args)
        except (AttributeError, ModuleNotFoundError) as ex:
            logging.getLogger("pipeman.netcdf").exception(f"Error loading netcdf field processor: {processor} ")


def _text_processor(attrs: dict, target_name: str, field: Field, config: dict, fc: FieldContainer):
    attrs[target_name] = field.data()


def _datetime_processor(attrs: dict, target_name: str, field: Field, config: dict, fc: FieldContainer):
    attrs[target_name] = field.data().isoformat()


def _vocab_processor(attrs: dict, target_name: str, field: Field, config: dict, fc: FieldContainer):
    attrs[target_name] = field.data()['short_name']


def _numeric_processor(attrs: dict, target_name: str, field: Field, config: dict, fc: FieldContainer):
    attrs[target_name] = field.data()


def _key_value_processor(attrs: dict, target_name: str, field: Field, config: dict, fc: FieldContainer):
    for key, val in field.data():
        attrs[key] = val


def _licenses_processor(attrs: dict, target_name: str, field: Field, config: dict, fc: FieldContainer):
    license_texts = []
    for uc in field.data():
        if uc['plain_text']:
            license_texts.append(uc["plain_text"])
    sep = "\n-----\n" if "sep" not in config else config["sep"]
    attrs[target_name] = sep.join(license_texts)


def _ref_system_processor(attrs: dict, target_name: str, field: Field, config: dict, fc: FieldContainer):
    ent = field.data()
    sys = ent['id_system']
    attrs[target_name] = f"{sys['code_space'] if sys else ''}{ent['code']}"


def _contact_role_processor(attrs: dict, target_prefix: str, field: Field, config: dict, fc: FieldContainer):
    for resp in field.data():
        if resp['role'] and resp['role']['short_name'] in config['role_map'] and resp['contact']:
            allow_many = False
            target_name = config['role_map'][resp['role']['short_name']]
            if target_name[-1] == '*':
                allow_many = True
                target_name = target_name[:-1]
            _contact_processor(attrs, target_name, resp['contact'], {'allow_many': allow_many})


def _contact_processor_initial(attrs: dict, target_prefix: str, field: Field, config: dict, fc: FieldContainer):
    _contact_processor(attrs, target_prefix, field.data(), config)


def _contact_processor(attrs: dict, target_prefix: str, contact: Entity, config: dict):
    contact_info = _extract_info(contact)
    if 'allow_many' in config and config['allow_many']:
        for x in contact_info:
            key = f"{target_prefix}_{x}"
            if key not in attrs:
                attrs[key] = contact_info[x]
            else:
                attrs[key] += "," + contact_info[x]
    else:
        for x in contact_info:
            attrs[f"{target_prefix}_{x}"] = contact_info[x]


def _extract_info(contact):
    subattrs = {}
    if contact['individual_name']:
        subattrs['name'] = contact['individual_name']
        subattrs['type'] = 'individual'
        if contact['organization_name']:
            subattrs['institution'] = contact['organization_name']
    elif contact['position_name']:
        subattrs['name'] = contact['position_name']
        subattrs['type'] = 'position'
        if contact['organization_name']:
            subattrs['institution'] = contact['organization_name']
    else:
        subattrs["name"] = contact['organization_name']
        subattrs[f"type"] = 'institution'
    if contact['email']:
        subattrs['email'] = contact['email']
    if contact['web_resource']:
        web_resource = contact['web_resource'][0]
        if web_resource['url']:
            subattrs[f'url'] = web_resource['url']
    return subattrs


def _variables(dataset):
    var_list = dataset['variables']
    _order = [(v, (v['variable_order'] or 0)) for v in var_list]
    _order.sort(key=lambda x: x[1])
    for var, _ in _order:
        yield (var['source_name'],
               var['source_data_type']['short_name'],
               " ".join(x.strip() for x in var['dimensions'].split(",")),
               _variable_attributes(var),
               var
               )


def _variable_attributes(var: Entity):
    attrs = _extract_netcdf_attributes(var)
    return attrs


@injector.injectable
class CFVocabularyManager:

    vtc: VocabularyTermController = None

    @injector.construct
    def __init__(self):
        self.log = logging.getLogger("pipeman.netcdf")

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
                    logging.getLogger("pipeman.netcdf").warning(f"Duplicate unit name detected: {symbol}")
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



