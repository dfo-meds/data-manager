import functools

from pipeman.builtins.iso19115.util import preprocess_metadata

ORIGINALS = {
    'CI_RoleCode': 'https://standards.iso.org/iso/19115/resources/Codelists/cat/codelists.xml#CI_RoleCode',
    'CI_DateTypeCode': 'http://standards.iso.org/iso/19115/resources/Codelists/cat/codelists.xml#CI_DateTypeCode',
    'CI_OnLineFunctionCode': 'https://standards.iso.org/iso/19115/resources/Codelists/cat/codelists.xml#CI_OnLineFunctionCode',
    'CI_PresentationFormCode': 'https://standards.iso.org/iso/19115/resources/Codelists/cat/codelists.xml#CI_PresentationFormCode',
    'MD_SpatialRepresentationTypeCode': 'https://standards.iso.org/iso/19115/resources/Codelists/cat/codelists.xml#MD_SpatialRepresentationTypeCode',
    'MD_ProgressCode': 'http://standards.iso.org/iso/19115/resources/Codelists/cat/codelists.xml#MD_ProgressCode',
    'MD_MaintenanceFrequencyCode': 'http://standards.iso.org/iso/19115/resources/Codelists/cat/codelists.xml#MD_MaintenanceFrequencyCode',
    'MD_KeywordTypeCode': 'http://standards.iso.org/iso/19115/resources/Codelists/cat/codelists.xml#MD_KeywordTypeCode',
    'MD_ClassificationCode': 'https://standards.iso.org/iso/19115/resources/Codelists/cat/codelists.xml#MD_ClassificationCode',
    'MD_RestrictionCode': 'https://standards.iso.org/iso/19115/resources/Codelists/cat/codelists.xml#MD_RestrictionCode',
    'CharacterSetCode': 'http://standards.iso.org/iso/19115/resources/Codelist/lan/CharacterSetCode.xml',
    'LanguageCode': 'http://standards.iso.org/iso/19115/resources/Codelist/lan/LanguageCode.xml',
    'CountryCode': 'http://standards.iso.org/iso/19115/resources/Codelists/cat/codelists.xml#CountryCode',
    'CI_TelephoneTypeCode': 'https://standards.iso.org/iso/19115/resources/Codelists/cat/codelists.xml#CI_TelephoneTypeCode',
}

NAP_CODE_LOOKUP = {
    'MD_MaintenanceFrequencyCode': {
        'list': 'http://nap.geogratis.gc.ca/metadata/register/napMetadataRegister.xml#IC_102',
        'values': {
            'continual': ('RI_532', 'continual'),
            'daily': ('RI_533', 'daily'),
            'weekly': ('RI_534', 'weekly'),
            'fortnightly': ('RI_535', 'fortnightly'),
            'monthly': ('RI_536', 'monthly'),
            'quarterly': ('RI_537', 'quaterly'),
            'biannually': ('RI_538', 'biannually'),
            'annually': ('RI_539', 'annually'),
            'asNeeded': ('RI_540', 'asNeeded'),
            'irregular': ('RI_541', 'irregular'),
            'notPlanned': ('RI_542', 'notPlanned'),
            'unknown': ('RI_543', 'unknown'),
            'semimonthly': ('RI_544', 'semimonthly'),
        }
    },
    'MD_KeywordTypeCode': {
        'list': 'http://nap.geogratis.gc.ca/metadata/register/napMetadataRegister.xml#IC_101',
        'values': {
            'discipline': ('RI_524', 'discipline'),
            'place': ('RI_525', 'place'),
            'stratum': ('RI_526', 'stratum'),
            'temporal': ('RI_527', 'temporal'),
            'theme': ('RI_528', 'theme'),
            'product': ('RI_529', 'product'),
            'subTopicCategory': ('RI_530', 'subTopicCategory'),
        }
    },
    'CountryCode': {
        'list': 'http://nap.geogratis.gc.ca/metadata/register/napMetadataRegister.xml#IC_117',
        'values': {
            'CAN': ('CAN', 'Canada'),
        }
    },
    'LanguageCode': {
        'list': 'http://nap.geogratis.gc.ca/metadata/register/napMetadataRegister.xml#IC_116',
        'values': {
            'fra': ('fra', 'French'),
            'eng': ('eng', 'English'),
        }
    },
    'MD_SpatialRepresentationTypeCode': {
        'list': 'http://nap.geogratis.gc.ca/metadata/register/napMetadataRegister.xml#IC_109',
        'values': {
            'vector': ('RI_635', 'vector'),
            'grid': ('RI_636', 'grid'),
            'textTable': ('RI_637', 'textTable'),
            'tin': ('RI_638', 'tin'),
            'stereoModel': ('RI_639', 'stereoModel'),
            'video': ('RI_640', 'video'),
        }
    },
    'CharacterSetCode': {
        'list': 'http://nap.geogratis.gc.ca/metadata/register/napMetadataRegister.xml#IC_95',
        'values': {
            'ucs2': ('RI_455', 'ucs2'),
            'ucs4': ('RI_456', 'ucs4'),
            'utf_7': ('RI_457', 'utf7'),
            'utf8': ('RI_458', 'utf8'),
            'utf16': ('RI_459', 'utf16'),
            'iso-8859-1': ('RI_460', '8859part1'),
            'iso-8859-2': ('RI_461', '8859part2'),
            'iso-8859-3': ('RI_462', '8859part3'),
            'iso-8859-4': ('RI_463', '8859part4'),
            'iso-8859-5': ('RI_464', '8859part5'),
            'iso-8859-6': ('RI_465', '8859part6'),
            'iso-8859-7': ('RI_466', '8859part7'),
            'iso-8859-8': ('RI_467', '8859part8'),
            'iso-8859-9': ('RI_468', '8859part9'),
            'iso-8859-10': ('RI_469', '8859part10'),
            'iso-8859-11': ('RI_470', '8859part11'),
            'iso-8859-13': ('RI_471', '8859part13'),
            'iso-8859-14': ('RI_472', '8859part14'),
            'iso-8859-15': ('RI_473', '8859part15'),
            'iso-8859-16': ('RI_474', '8859part16'),
            'JIS_Encoding': ('RI_475', 'jis'),
            'shift_jis': ('RI_476', 'shiftJIS'),
            'euc_jp': ('RI_477', 'eucJP'),
            'ascii': ('RI_478', 'usascii'),
            'ebcdic': ('RI_479', 'ebcdic'),
            'euc_kr': ('RI_480', 'eucKR'),
            'big5': ('RI_481', 'big5'),
            'gb2312': ('RI_482', 'GB2312'),
        }
    },
    'MD_ClassificationCode': {
        'list': 'http://nap.geogratis.gc.ca/metadata/register/napMetadataRegister.xml#IC_96',
        'values': {
            'unclassified': ('RI_484', 'unclassified'),
            'restricted': ('RI_485', 'restricted'),
            'confidential': ('RI_486', 'confidential'),
            'secret': ('RI_487', 'secret'),
            'topSecret': ('RI_488', 'topSecret'),
            #'sensitive': ('RI_489', 'sensitive'),
            'forOfficialUseOnly': ('RI_490', 'forOfficialUseOnly'),
        }
    },
    'CI_DateTypeCode': {
        'list': 'http://nap.geogratis.gc.ca/metadata/register/napMetadataRegister.xml#IC_87',
        'values': {
            'creation': ('RI_366', 'creation'),
            'publication': ('RI_367', 'publication'),
            'revision': ('RI_368', 'revision'),
            'unavailable': ('RI_369', 'notAvailable'),
            'inForce': ('RI_370', 'inForce'),
            'adopted': ('RI_371', 'adopted'),
            'deprecated': ('RI_372', 'deprecated'),
            'superseded': ('RI_373', 'superseded'),
        }
    },
    'MD_RestrictionCode': {
        'list': 'http://nap.geogratis.gc.ca/metadata/register/napMetadataRegister.xml#IC_107',
        'values': {
            'copyright': ('RI_602', 'copyright'),
            'patent': ('RI_603', 'patent'),
            'patentPending': ('RI_604', 'patentPending'),
            'trademark': ('RI_605', 'trademark'),
            'license': ('RI_606', 'license'),
            'intellectualPropertyRights': ('RI_607', 'intellectualPropertyRights'),
            'restricted': ('RI_608', 'restricted'),
            'otherRestrictions': ('RI_609', 'otherRestrictions'),
            'licenseUnrestricted': ('RI_610', 'licenseUnrestricted'),
            'licenseEndUser': ('RI_611', 'licenseEndUser'),
            'licenseDistributor': ('RI_612', 'licenseDistributor'),
            'private': ('RI_613', 'privacy'),
            'statutory': ('RI_614', 'statutory'),
            'confidential': ('RI_615', 'confidential'),
            #'sensitivity': ('RI_616', 'sensitivity'),
        }
    },
    'CI_PresentationFormCode': {
        'list': 'http://nap.geogratis.gc.ca/metadata/register/napMetadataRegister.xml#IC_89',
        'values': {
            'documentDigital': ('RI_387', 'documentDigital'),
            'documentHardcopy': ('RI_388', 'documentHardcopy'),
            'imageDigital': ('RI_389', 'imageDigital'),
            'imageHardcopy': ('RI_390', 'imageHardcopy'),
            'mapDigital': ('RI_391', 'mapDigital'),
            'mapHardcopy': ('RI_392', 'mapHardcopy'),
            'modelDigital': ('RI_393', 'modelDigital'),
            'modelHardcopy': ('RI_394', 'modelHardcopy'),
            'profileDigital': ('RI_395', 'profileDigital'),
            'profileHardcopy': ('RI_396', 'profileHardcopy'),
            'tableDigital': ('RI_397', 'tableDigital'),
            'tableHardcopy': ('RI_398', 'tableHardcopy'),
            'videoDigital': ('RI_399', 'videoDigital'),
            'videoHardcopy': ('RI_400', 'videoHardcopy'),
            'audioDigital': ('RI_401', 'audioDigital'),
            'audioHardcopy': ('RI_402', 'audioHardcopy'),
            'multimediaDigital': ('RI_403', 'multimediaDigital'),
            'multimediaHardcopy': ('RI_404', 'multimediaHardcopy'),
            'diagramDigital': ('RI_405', 'diagramDigital'),
            'diagramHardcopy': ('RI_406', 'diagramHardcopy'),
        }
    },
    'CI_OnLineFunctionCode': {
        'list': 'http://nap.geogratis.gc.ca/metadata/register/napMetadataRegister.xml#IC_88',
        'values': {
            'download': ('RI_375', 'download'),
            'information': ('RI_376', 'information'),
            'offlineAccess': ('RI_377', 'offlineAccess'),
            'order': ('RI_378', 'order'),
            'search': ('RI_379', 'search'),
            'upload': ('RI_380', 'upload'),
            'webService': ('RI_381', 'webService'),
            'emailService': ('RI_382', 'emailService'),
            'browsing': ('RI_383', 'browsing'),
            'fileAccess': ('RI_384', 'fileAccess'),
            'webMapService': ('RI_385', 'webMapService'),
        }
    },
    'MD_ProgressCode': {
        'list': 'http://nap.geogratis.gc.ca/metadata/register/napMetadataRegister.xml#IC_106',
        'values': {
            'completed': ('RI_593', 'completed'),
            'historicalArchive': ('RI_594', 'historicalArchive'),
            'obsolete': ('RI_595', 'obsolete'),
            'onGoing': ('RI_596', 'onGoing'),
            'planned': ('RI_597', 'planned'),
            'required': ('RI_598', 'required'),
            'underDevelopment': ('RI_599', 'underDevelopment'),
            'proposed': ('RI_600', 'proposed'),
        }
    },
    'CI_RoleCode': {
        'list': 'http://nap.geogratis.gc.ca/metadata/register/napMetadataRegister.xml#IC_90',
        'values': {
            'resourceProvider': ('RI_408', 'resourceProvider'),
            'custodian': ('RI_409', 'custodian'),
            'owner': ('RI_410', 'owner'),
            'user': ('RI_411', 'user'),
            'distributor': ('RI_412', 'distributor'),
            'originator': ('RI_413', 'originator'),
            'pointOfContact': ('RI_414', 'pointOfContact'),
            'principalInvestigator': ('RI_415', 'principalInvestigator'),
            'processor': ('RI_416', 'processor'),
            'publisher': ('RI_417', 'publisher'),
            'author': ('RI_418', 'author'),
            'collaborator': ('RI_419', 'collaborator'),
            'editor': ('RI_420', 'editor'),
            'mediator': ('RI_421', 'mediator'),
            'rightsHolder': ('RI_422', 'rightsHolder'),

        }
    }
}


def nap_code_map(code, code_list):
    if code_list in NAP_CODE_LOOKUP and code in NAP_CODE_LOOKUP[code_list]['values']:
        return NAP_CODE_LOOKUP[code_list]['list'], *NAP_CODE_LOOKUP[code_list]['values'][code]
    return ORIGINALS[code_list], code, code


def preprocess_for_nap(*args, **kwargs):
    keys = preprocess_metadata(*args, **kwargs)
    keys['nap_code_map'] = nap_code_map
    return keys
