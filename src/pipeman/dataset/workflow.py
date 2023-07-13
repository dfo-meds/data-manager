from autoinject import injector
from pipeman.db import Database
import pipeman.db.orm as orm
from pipeman.workflow import ItemResult
import datetime
import zrlog
from pipeman.email import EmailController
from pipeman.dataset import DatasetController
import typing as t

from pipeman.workflow.steps import WorkflowStep


@injector.inject
def publish_dataset(step, context, db: Database = None):
    log = zrlog.get_logger("pipeman.dataset")
    with db as session:
        ds = session.query(orm.Dataset).filter_by(id=context["dataset_id"]).first()
        if not ds:
            log.warning(f"Invalid dataset ID [{context['dataset_id']}]")
            step.output.append(f"Invalid dataset ID [{context['dataset_id']}]")
            return ItemResult.FAILURE
        md = session.query(orm.MetadataEdition).filter_by(id=context["metadata_id"]).first()
        if not md:
            log.warning(f"Invalid dataset metadata ID [{context['metadata_id']}]")
            step.output.append(f"Invalid dataset metadata ID [{context['metadata_id']}]")
            return ItemResult.FAILURE
        md.is_published = True
        md.published_date = datetime.datetime.now()
        md.approval_item_id = step.item.id
        session.commit()
        log.info(f"Dataset [{context['dataset_id']}] publish status updated successfully")
        return ItemResult.SUCCESS


@injector.inject
def activate_dataset(step, context, db: Database = None):
    log = zrlog.get_logger("pipeman.dataset")
    with db as session:
        ds = session.query(orm.Dataset).filter_by(id=context["dataset_id"]).first()
        if not ds:
            log.warning(f"Invalid dataset ID [{context['dataset_id']}]")
            step.output.append(f"Invalid dataset ID [{context['dataset_id']}]")
            return ItemResult.FAILURE
        ds.status = "ACTIVE"
        ds.activated_item_id = step.item.id
        session.commit()
        log.info(f"Dataset [{context['dataset_id']}] activated successfully")
        return ItemResult.SUCCESS


@injector.inject
def flag_dataset_for_review(step, context, db: Database = None):
    log = zrlog.get_logger("pipeman.dataset")
    with db as session:
        ds = session.query(orm.Dataset).filter_by(id=context["dataset_id"]).first()
        if not ds:
            log.warning(f"Invalid dataset ID [{context['dataset_id']}]")
            step.output.append(f"Invalid dataset ID [{context['dataset_id']}]")
            return ItemResult.FAILURE
        ds.status = "UNDER_REVIEW"
        session.commit()
        log.info(f"Dataset [{context['dataset_id']}] flagged for review")
        return ItemResult.SUCCESS


@injector.inject
def return_to_draft(step, context, db: Database = None):
    log = zrlog.get_logger("pipeman.dataset")
    with db as session:
        ds = session.query(orm.Dataset).filter_by(id=context["dataset_id"]).first()
        if not ds:
            log.warning(f"Invalid dataset ID [{context['dataset_id']}]")
            step.output.append(f"Invalid dataset ID [{context['dataset_id']}]")
            return ItemResult.FAILURE
        ds.status = "DRAFT"
        session.commit()
        log.info(f"Dataset [{context['dataset_id']}] returned to draft")
        return ItemResult.SUCCESS


@injector.inject
def send_dataset_action_email(step: WorkflowStep, context: dict, emails: EmailController):
    by_lang_pref = _email_list_for_step(step, context)
    for lang_pref in by_lang_pref:
        emails.send_template(
            step.item_config['email_template'],
            lang_pref,
            to_emails=by_lang_pref[lang_pref],
            immediate=True
        )


@injector.inject
def _email_list_for_step(step: WorkflowStep, context: dict, dc: DatasetController) -> t.Mapping[str, t.List[str]]:
    by_lang_pref = {}
    # TODO
    #for user in _email_list_for_step(step, context):
    #   if user.language_preference not in by_lang_pref:
    #        by_lang_pref[user.language_preference] = []
    #    by_lang_pref[user.language_preference].append(user.email)
    return by_lang_pref


