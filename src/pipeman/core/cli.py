import pathlib

import click
import yaml
from autoinject import injector
from pipeman.org import OrganizationController
from pipeman.workflow import WorkflowController
from pipeman.util import System
from pipeman.dataset import MetadataRegistry
from pipeman.vocab import VocabularyTermController, VocabularyRegistry
from pipeman.entity import EntityRegistry
from pipeman.workflow import WorkflowRegistry
import asyncio
import csv


@click.group
def org():
    pass


@org.command
@click.argument("org_name")
@injector.inject
def create(org_name, org_controller: OrganizationController = None):
    org_controller.upsert_organization(org_name)


@click.group
def workflow():
    pass


@workflow.command
@injector.inject
def batch(wfc: WorkflowController):
    wfc.batch_process_items()


@workflow.command
@injector.inject
def async_batch(wfs: WorkflowController):
    asyncio.run(wfs.async_batch_process_items())


@click.group
def core():
    pass


@core.command
@injector.inject
def setup(system: System = None):
    system.setup()


@core.command
@injector.inject
def cleanup(system: System = None):
    system.cleanup()


@core.command
def cron():
    from pipeman.util.cron import CronDaemon
    daemon = CronDaemon()
    daemon.run_forever()


@click.group
def report():
    pass


@report.command
@click.argument('output_file')
@injector.inject
def entity_types(output_file, ereg: EntityRegistry = None):
    with open(output_file, "w", newline="\n", encoding="utf-8") as h:
        writer = csv.writer(h)
        ets = dict(ereg.list_entity_types())
        writer.writerow([
            'entity_type',
            'is_component',
            'name_en',
            'name_fr',
        ])
        for et in ets:
            writer.writerow([
                et,
                'true' if 'is_component' in ets[et] and ets[et]['is_component'] else 'false',
                ets[et]['display']['en'] if 'en' in ets[et]['display'] else '',
                ets[et]['display']['fr'] if 'fr' in ets[et]['display'] else ''
            ])


@report.command
@click.argument('output_file')
@injector.inject
def entity_fields(output_file, ereg: EntityRegistry = None):
    with open(output_file, "w", newline="\n", encoding="utf-8") as h:
        writer = csv.writer(h)
        ets = dict(ereg.list_entity_types())
        writer.writerow([
            'entity_type',
            'field_name',
            'order',
            'data_type',
            'name_und',
            'name_en',
            'name_fr',
        ])
        for et in ets:
            if not ('fields' in ets[et] and ets[et]['fields']):
                continue
            fields = ets[et]['fields']
            for fn in fields:
                output = [
                    et,
                    fn,
                    fields[fn]['order'] if 'order' in fields[fn] else '',
                    fields[fn]['data_type'],
                    fields[fn]['label']['und'] if 'und' in fields[fn]['label'] else '',
                    fields[fn]['label']['en'] if 'en' in fields[fn]['label'] else '',
                    fields[fn]['label']['fr'] if 'fr' in fields[fn]['label'] else '',
                ]
                writer.writerow(output)


@report.command
@click.argument('output_file')
@injector.inject
def fields(output_file, mreg: MetadataRegistry = None):
    with open(output_file, "w", newline="\n", encoding="utf-8") as h:
        writer = csv.writer(h)
        profiles = dict(mreg.profiles_for_select())
        fields = dict(mreg.field_list())
        writer.writerow([
            'field_name',
            'display_group',
            'order',
            'data_type',
            'name_und',
            'name_en',
            'name_fr',
            'profiles',
        ])
        for fn in fields:
            output = [
                fn,
                fields[fn]["display_group"],
                fields[fn]['order'] if 'order' in fields[fn] else '',
                fields[fn]['data_type'],
                fields[fn]['label']['und'] if 'und' in fields[fn]['label'] else '',
                fields[fn]['label']['en'] if 'en' in fields[fn]['label'] else '',
                fields[fn]['label']['fr'] if 'fr' in fields[fn]['label'] else '',
            ]
            pro = [p for p in profiles if mreg.profile_contains_field(p, fn)]
            output.append(';'.join(pro) if pro else '')
            writer.writerow(output)


@report.command
@click.argument("output_file")
@injector.inject
def vocabularies(output_file, vreg: VocabularyRegistry):
    with open(output_file, "w", newline="\n", encoding="utf-8") as h:
        writer = csv.writer(h)
        writer.writerow(["vocabulary_name", "uri", "name_und", "name_en", "name_fr"])
        for name, display, uri in vreg.list_vocabularies():
            writer.writerow([
                name,
                uri,
                display['und'] if 'und' in display else '',
                display['en'] if 'en' in display else '',
                display['fr'] if 'fr' in display else ''
            ])


@report.command
@click.argument("output_file")
@injector.inject
def terms(output_file, vreg: VocabularyRegistry, vtc: VocabularyTermController):
    with open(output_file, "w", newline="\n", encoding="utf-8") as h:
        writer = csv.writer(h)
        writer.writerow(["vocabulary_name", "term_name", "name_und", "name_en", "name_fr", "description_und", "description_en", "description_fr"])
        for name, display, uri in vreg.list_vocabularies():
            for tname, tdisp, tdesc in vtc.list_terms(name):
                writer.writerow([
                    name,
                    tname,
                    tdisp['und'] if 'und' in tdisp else '',
                    tdisp['en'] if 'en' in tdisp else '',
                    tdisp['fr'] if 'fr' in tdisp else '',
                    tdesc['und'] if 'und' in tdesc else '',
                    tdesc['en'] if 'en' in tdesc else '',
                    tdesc['fr'] if 'fr' in tdesc else ''
                ])


@report.command
@click.argument("output_file")
@injector.inject
def workflows(output_file, wreg: WorkflowRegistry):
    with open(output_file, "w", newline="\n", encoding="utf-8") as h:
        writer = csv.writer(h)
        writer.writerow([
            "workflow_name",
            "enabled",
            "steps",
            "cleanup_steps",
            "name_en",
            "name_fr"
        ])
        workflows = dict(wreg.list_all_workflows())
        for wf in workflows:
            writer.writerow([
                wf,
                'false' if "enabled" in workflows[wf] and not workflows[wf]['enabled'] else 'true',
                ";".join(workflows[wf]["steps"]) if "steps" in workflows[wf] else "",
                ";".join(workflows[wf]["cleanup"]) if "cleanup" in workflows[wf] else "",
                workflows[wf]["label"]["en"] if "en" in workflows[wf]["label"] else "",
                workflows[wf]["label"]["fr"] if "fr" in workflows[wf]["label"] else "",
            ])


@report.command
@click.argument("output_file")
@injector.inject
def steps(output_file, wreg: WorkflowRegistry):
    with open(output_file, "w", newline="\n", encoding="utf-8") as h:
        writer = csv.writer(h)
        writer.writerow([
            "step_name",
            "step_type",
            "action_call",
            "name_en",
            "name_fr",
        ])
        steps = dict(wreg.list_all_steps())
        for sn in steps:
            writer.writerow([
                sn,
                steps[sn]["step_type"],
                steps[sn]["action"] if "action" in steps[sn] else (steps[sn]["coro"] if "coro" in steps[sn] else ""),
                steps[sn]["label"]["en"] if "en" in steps[sn]["label"] else "",
                steps[sn]["label"]["fr"] if "fr" in steps[sn]["label"] else "",
            ])


@report.command
@click.argument("output_file")
@injector.inject
def translations(output_file, wreg: WorkflowRegistry, vreg: VocabularyRegistry, vtc: VocabularyTermController, mreg: MetadataRegistry, ereg: EntityRegistry):
    skip_complete: int = 1
    with open(output_file, "w", newline="\n", encoding="utf-8") as h:
        writer = csv.writer(h)
        writer.writerow([
            "category",
            "element",
            "sub-element",
            "sub-element2",
            "name_und",
            "name_en",
            "name_fr"
        ])
        workflows = dict(wreg.list_all_workflows())
        for wf in workflows:
            if _check_output(workflows[wf]["label"], skip_complete):
                writer.writerow([
                    "workflow_workflows",
                    wf,
                    "label",
                    "",
                    *_extract_text_parts(workflows[wf]["label"])
                ])
        steps = dict(wreg.list_all_steps())
        for sn in steps:
            if _check_output(steps[sn]["label"], skip_complete):
                writer.writerow([
                    "workflow_steps",
                    sn,
                    "label",
                    "",
                    *_extract_text_parts(steps[sn]["label"])
                ])
        for name, display, uri in vreg.list_vocabularies():
            for tname, tdisp, tdesc in vtc.list_terms(name):
                if _check_output(tdisp, skip_complete):
                    writer.writerow([
                        "vocabulary_terms",
                        name,
                        tname,
                        'label',
                        *_extract_text_parts(tdisp)
                    ])
                if _check_output(tdesc, skip_complete):
                    writer.writerow([
                        "vocabulary_terms",
                        name,
                        tname,
                        'description',
                        * _extract_text_parts(tdesc)
                    ])
        ets = dict(ereg.list_entity_types(True))
        for en in ets:
            if _check_output(ereg.display(en), skip_complete):
                writer.writerow([
                    "entity_types",
                    en,
                    "label",
                    "",
                    *_extract_text_parts(ereg.display(en))
                ])
            if not ('fields' in ets[en] and ets[en]['fields']):
                continue
            fields = ets[en]['fields']
            for fn in fields:
                if _check_output(fields[fn]["label"], skip_complete):
                    writer.writerow([
                        "entity_types",
                        en,
                        fn,
                        "label",
                        *_extract_text_parts(fields[fn]['label'])
                    ])
                if 'description' not in fields[fn] or _check_output(fields[fn]['description'], skip_complete):
                    writer.writerow([
                        "entity_types",
                        en,
                        fn,
                        "description",
                        *_extract_text_parts(fields[fn]['description'] if 'description' in fields[fn] else {})
                    ])
        profiles = dict(mreg.profiles_for_select())
        for pname in profiles:
            if _check_output(mreg.profile_label(pname), skip_complete):
                writer.writerow([
                    "profile",
                    pname,
                    "label",
                    "",
                    *_extract_text_parts(mreg.profile_label(pname))
                ])
        fields = dict(mreg.field_list())
        for fn in fields:
            if _check_output(fields[fn]['label'], skip_complete):
                writer.writerow([
                    "field",
                    fn,
                    "label",
                    "",
                    *_extract_text_parts(fields[fn]['label'])
                ])
            if 'description' not in fields[fn] or _check_output(fields[fn]['description'], skip_complete):
                writer.writerow([
                    "field",
                    fn,
                    "description",
                    "",
                    *_extract_text_parts(fields[fn]['description'] if 'description' in fields[fn] else {})
                ])
        root = pathlib.Path(__file__).absolute().parent.parent.parent.parent / "config" / "locales"
        if root.exists():
            en_file = root / "en.yaml"
            fr_file = root / "fr.yaml"
            en_list = {}
            fr_list = {}
            if en_file.exists():
                with open(en_file, "r", encoding="utf-8") as h:
                    en_list = yaml.safe_load(h.read()) or {}
            if fr_file.exists():
                with open(fr_file, "r", encoding="utf-8") as h:
                    fr_list = yaml.safe_load(h.read()) or {}
            keys = set(x for x in en_list)
            keys.update(x for x in fr_list)
            for k in sorted(keys):
                if skip_complete and k in en_list and k in fr_list and en_list[k] and fr_list[k]:
                    continue
                writer.writerow([
                    "i18n",
                    k,
                    "",
                    "",
                    "",
                    en_list[k] if k in en_list else "",
                    fr_list[k] if k in fr_list else ""
                ])


def _check_output(txt, skip_complete: int):
    if skip_complete in (1,2) and ('en' in txt and 'fr' in txt and txt['en'] and txt['fr']):
        return False
    if skip_complete == 2 and 'und' in txt and txt['und']:
        return False
    return True

def _extract_text_parts(txt):
    return [
        txt[x] if x in txt else ''
        for x in ('und', 'en', 'fr')
    ]
