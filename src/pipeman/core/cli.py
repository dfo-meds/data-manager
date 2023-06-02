import click
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
    from .util import CronDaemon
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
