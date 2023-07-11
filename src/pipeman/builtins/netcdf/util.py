import json

import netCDF4._netCDF4
import numpy
import requests

from pipeman.util.flask import ActionList
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
import zrlog
import datetime
import functools

UTC = datetime.timezone(datetime.timedelta(seconds=0), "UTC")


def netcdf_dataset_actions(items: ActionList, dataset, short_list: bool = True, for_revision: bool = False):
    if not (short_list or for_revision):
        items.add_action("pipeman.netcdf.page.populate_from_netcdf.link",
                         "netcdf.populate_from_netcdf_dsid",
                         30,
                         dataset_id=dataset.dataset_id if hasattr(dataset, "dataset_id") else dataset.id)


def preprocess_for_ncml(dataset, **kwargs):
    extras = _preprocess_for_both(dataset, **kwargs)
    return extras


def preprocess_for_cdl(dataset, **kwargs):
    extras = _preprocess_for_both(dataset, **kwargs)
    return extras


def _has_other_languages(language_dict, default_locale, supported_locales):
    for key in language_dict:
        if key == "und" or key == default_locale:
            continue
        if key not in supported_locales:
            continue
        return True
    return False


def _preprocess_for_both(dataset, **kwargs):
    locale_mapping = {}
    def_loc = dataset.data("default_locale")
    default_locale = def_loc['a2_language'] if def_loc else "en"
    default_country = def_loc['country'] if def_loc and def_loc['country'] else "CAN"
    default_charset = def_loc['encoding']['short_name'] if def_loc and def_loc['encoding'] else "utf8"
    locale_mapping[default_locale] = def_loc['language'] if def_loc else "eng"
    olocales = dataset.data("other_locales") or []
    supported_keys = []
    supported = []
    for other_loc in olocales:
        locale_mapping[other_loc['a2_language']] = other_loc['language']
        name = other_loc['a2_language']
        if other_loc['country']:
            name += f'-{other_loc["country"]}'
        if other_loc['encoding']:
            name += f';{other_loc["encoding"]["short_name"]}'
        supported.append(f"{other_loc['a2_language']}:{name}")
        supported_keys.append(other_loc['a2_language'])
    extras = {
        'global_attributes': _global_attributes(dataset),
        'variables': _variables(dataset),
        'locale_mapping': locale_mapping,
        'default_locale': default_locale,
        'check_alt_langs': functools.partial(_has_other_languages, supported_locales=supported_keys),
    }
    extras['global_attributes']['locale_default'] = f"{default_locale}-{default_country};{default_charset}"
    extras['global_attributes']['locale_others'] = ",".join(supported)
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
    extras['global_attributes']['keywords'] = ','.join(keywords)
    extras['global_attributes']['keywords_vocabulary'] = ','.join(vocabularies)
    return extras


def _autodetect_mapping(field: Field):
    dt = field.config('data_type')
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
    attrs['naming_authority'] = dataset.naming_authority()
    return attrs


@injector.inject
def set_metadata_from_netcdf(dataset: Dataset, file_type: str, metadata: dict, ec: EntityController = None, vtc: VocabularyTermController = None):
    if 'keywords' in metadata['global']:
        _process_keywords(dataset, metadata['global'].pop('keywords'), ec)
    _import_netcdf_attributes(dataset, metadata['global'], 'custom_metadata')
    variables = dataset.get_field('variables')
    current_list = {}
    for c, _, _ in variables.component_list():
        c_ent = ec.load_entity(c.entity_type, c.id)
        current_list[c_ent.data('source_name')] = c_ent
    for var_name in metadata['variables'] or []:
        var_attrs = metadata['variables'][var_name]
        if var_name not in current_list:
            real_var = ec.reg.new_entity('variable')
            real_var.set_display_name('und', var_name)
            real_var.parent_id = dataset.dataset_id
            real_var.parent_type = 'dataset'
            real_var.get_field('source_name').set_from_raw(var_name)
        else:
            real_var = current_list[var_name]
        if '_data_type' in var_attrs:
            dt = var_attrs.pop('_data_type')
            data_type = vtc.get_term_name('netcdf_data_types', _map_netcdf_datatype_to_erddap(dt))
            if data_type:
                real_var.get_field('source_data_type').set_from_raw(data_type)
            else:
                zrlog.get_logger('pipeman.netcdf').warning(f"NetCDF datatype {dt} not recognized")
        if '_dimensions' in var_attrs:
            real_var.get_field('dimensions').set_from_raw(','.join(var_attrs.pop('_dimensions')))
        _import_netcdf_attributes(real_var, var_attrs, 'custom_metadata')
        ec.save_entity(real_var)


def _process_keywords(dataset: Dataset, keywords: str, ec: EntityController):
    _custom_map = None
    for keyword in keywords.split(","):
        dict_name = None
        if ':' in keyword:
            dict_name, keyword = keyword.split(":")
        keyword = keyword.strip("\r\n\t ")
        dict_name = dict_name.strip("\r\n\t ")
        if keyword == "":
            continue
        for field in dataset.ordered_field_names():
            if dataset.get_field(field).update_from_keyword(keyword, dict_name):
                break
        else:
            field = dataset.get_field('custom_keywords')
            if _custom_map is None:
                _custom_map = {
                    'thesaurus': {},
                    'keywords': []
                }
                for t, _, _ in ec.list_entities('thesaurus'):
                    content = json.loads(t.latest_revision().data) if t.latest_revision() else {}
                    if 'prefix' in content and content['prefix']:
                        _custom_map['thesaurus'][str(t.id)] = content['prefix']
                for t, _, _ in ec.list_entities('keyword'):
                    content = json.loads(t.latest_revision().data) if t.latest_revision() else {}
                    prefix = None
                    thesaurus_id = None
                    if 'thesaurus' in content:
                        thesaurus_id = int(content['thesaurus']) if content['thesaurus'] else None
                        if str(content['thesaurus']) in _custom_map['thesaurus']:
                            prefix = _custom_map['thesaurus'][str(thesaurus_id)]
                    keywords = set([content['keyword'][x] for x in content['keyword'] if x[0] != '_' and content['keyword'][x]]) if 'keyword' in content and content['keyword'] else {}
                    _custom_map['keywords'].append((keywords, thesaurus_id, prefix, t.id))
            for kws, tid, prefix, kid in _custom_map['keywords']:
                if prefix is not None and dict_name is not None and dict_name != prefix:
                    continue
                if keyword not in kws:
                    continue
                values = field.value
                values.append(kid)
                field.set_from_raw(list(set(values)))
                break
            else:
                actual_tid = None
                if dict_name is not None:
                    for tid in _custom_map['thesaurus']:
                        if _custom_map['thesaurus'] == dict_name:
                            actual_tid = str(tid)
                            break
                    else:
                        new_t = ec.reg.new_entity('thesaurus')
                        new_t.get_field('prefix').set_from_raw(dict_name)
                        ec.save_entity(new_t)
                        _custom_map['thesaurus'][str(new_t.db_id)] = dict_name
                        actual_tid = str(new_t.db_id)
                new_k = ec.reg.new_entity('keyword')
                new_k.set_display_name('und', keyword)
                new_k.get_field('keyword').set_from_raw({"und": keyword})
                new_k.get_field('thesaurus').set_from_raw(actual_tid)
                ec.save_entity(new_k)
                _custom_map['keywords'].append(({keyword}, actual_tid, dict_name, new_k.db_id))
                values = field.value
                values.append(new_k.db_id)
                field.set_from_raw(list(set(values)))


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
        elif 'processor' in config and config['processor'] and "." not in config['processor']:
            processor = config['processor']
        else:
            processor = _autodetect_mapping(field)
        if processor is not None:
            _import_field_value(processor, config, attributes, fc, field)
    if extra_field_name:
        extras = fc.get_field(extra_field_name)
        values = {
            v['key']: v
            for v in extras.value
        } if extras.value else {}
        for attr in attributes:
            if attr[0] == '_':
                continue
            val = attributes[attr]
            dtype = 'str'
            if isinstance(val, int) or isinstance(val, float) or isinstance(val, numpy.int8) or isinstance(val, numpy.float64):
                dtype = 'numeric'
            elif isinstance(val, list) or isinstance(val, tuple) or isinstance(val, numpy.ndarray):
                dtype = 'numeric_list'
                val = ','.join(str(x) for x in val)
            values[attr] = {
                'key': attr,
                'value': str(val),
                'data_type': dtype
            }
        extras.set_from_raw([values[x] for x in values])


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
    elif processor == "licenses":
        _import_license(*args)
    else:
        try:
            obj = load_object(processor)
            obj(*args)
        except (AttributeError, ModuleNotFoundError) as ex:
            logging.getLogger("pipeman.netcdf").exception(f"Error loading netcdf field importer: {processor} ")


def _import_license(config: dict, attributes: dict, fc: FieldContainer, field: Field):
    pass


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
        # Pre 3.11, doesn't handle time zones so we'll fake support for that.
        if dt.endswith('Z') or (len(dt) > 6 and dt[-6] in ('+', '-')):
            if dt.endswith('Z'):
                dt_ = datetime.datetime.fromisoformat(dt[:-1])
                field.set_from_raw(dt_.replace(tzinfo=UTC))
            else:
                dt_ = datetime.datetime.fromisoformat(dt[:-6])
                offset = int(dt[-5:-3]) * 3600
                offset += int(dt[-2:]) * 60
                offset *= -1 if dt[-6] == '-' else 1
                field.set_from_raw(dt_.replace(tzinfo=datetime.timezone(datetime.timedelta(seconds=offset))).astimezone(tz=UTC))
        else:
            dt_ = datetime.datetime.fromisoformat(dt[:-1])
            field.set_from_raw(dt_.replace(tzinfo=UTC))


def _import_ref_system(config: dict, attributes: dict, fc: FieldContainer, field: Field):
    # TODO
    pass


def _import_contact(config: dict, attributes: dict, fc: FieldContainer, field: Field):
    # TODO
    pass


def _import_contacts_by_role(config: dict, attributes: dict, fc: FieldContainer, field: Field):
    # TODO
    pass


def _map_netcdf_datatype_to_erddap(netcdf_dt: str) -> str:
    if isinstance(netcdf_dt, netCDF4._netCDF4.VLType):
        netcdf_dt = netcdf_dt.dtype
    if netcdf_dt == 'str' or netcdf_dt == str:
        return 'String'
    if netcdf_dt in ('S1', 'c'):
        return 'char'
    if netcdf_dt in ('i2', 'h', 's'):
        return 'short'
    if netcdf_dt in ('i1', 'b', 'B'):
        return 'byte'
    if netcdf_dt in ('i', 'l', 'i4'):
        return 'int'
    if netcdf_dt in ('f', 'f4'):
        return 'float'
    if netcdf_dt in ('d', 'f8'):
        return 'double'
    if netcdf_dt == 'i8':
        return 'long'
    if netcdf_dt == 'u8':
        return 'ulong'
    if netcdf_dt == 'u4':
        return 'uint'
    if netcdf_dt == 'u2':
        return 'ushort'
    if netcdf_dt == 'u1':
        return 'ubyte'
    raise ValueError(f'Unrecognized NetCDF datatype: {netcdf_dt}')


@injector.inject
def _import_vocab_value(config: dict, attributes: dict, fc: FieldContainer, field: Field, vtc: VocabularyTermController = None):
    target = config["mapping"]
    sep = config['separator'] if 'separator' in config and config['separator'] else ','
    if target in attributes and attributes[target]:
        if 'allow_many' in config and config['allow_many']:
            term_ids = set()
            skipped = []
            for term_name in attributes.pop(target).split(sep):
                term_id = vtc.get_term_name(field.config('vocabulary_name'), term_name.strip())
                if term_id:
                    term_ids.add(term_id)
                else:
                    skipped.append(term_name)
            if skipped:
                attributes[target] = sep.join(skipped)
            if term_ids:
                field.set_from_raw(term_ids)
        else:
            term_id = vtc.get_term_name(field.config('vocabulary_name'), attributes[target].strip())
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
    if not field.is_empty():
        attrs[target_name] = field.data().isoformat()


def _vocab_processor(attrs: dict, target_name: str, field: Field, config: dict, fc: FieldContainer):
    values = []
    if 'allow_many' in config and config['allow_many']:
        for x in field.data():
            if x is not None:
                if not isinstance(x, dict):
                    zrlog.get_logger("pipeman.netcdf").error(f"Field {target_name} is supposed to be a list of dicts, but is actually a list of {type(x)}")
                    continue
                else:
                    values.append(x['short_name'])
    else:
        val = field.data()
        if val is not None:
            if not isinstance(val, dict):
                zrlog.get_logger("pipeman.netcdf").error(f"Field {target_name} is supposed to be a list of dicts, but is actually a list of {type(val)}")
            else:
                values.append(val['short_name'])
    if values:
        attrs[target_name] = ",".join(values)


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
    sep = config['separator'] if 'separator' in config and config['separator'] else ','
    if 'allow_many' in config and config['allow_many']:
        for x in contact_info:
            key = f"{target_prefix}_{x}"
            if key not in attrs:
                attrs[key] = contact_info[x]
            else:
                attrs[key] += sep + contact_info[x]
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
               var['source_data_type']['short_name'] if var['source_data_type'] else "?",
               " ".join(x.strip() for x in var['dimensions'].split(",")) if var['dimensions'] else '',
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
        self.log.info(f"Loading CF standard names")
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
        self.log.info("Loading UDUnit prefixes")
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
        self.log.info(f"Loading UDUnit units")
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
                        "und": f"{name} [{symbol}]" if symbol != name else name,
                    },
                    "description": {
                        "en": desc,
                    }
                }
        self.log.info(f"Found {len(terms)} udunit units")
        self.vtc.save_terms_from_dict("udunit_units", terms)



