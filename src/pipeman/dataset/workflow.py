from autoinject import injector
from pipeman.db import Database
import pipeman.db.orm as orm
from pipeman.workflow import ItemResult
import datetime


@injector.inject
def publish_dataset(action_config, context, db: Database = None):
    with db as session:
        ds = session.query(orm.Dataset).filter_by(id=context["dataset_id"]).first()
        if not ds:
            return ItemResult.FAILURE
        md = session.query(orm.MetadataEdition).filter_by(id=context["metadata_id"]).first()
        if not md:
            return ItemResult.FAILURE
        md.is_published = True
        md.published_date = datetime.datetime.now()
        session.commit()
        return ItemResult.SUCCESS


@injector.inject
def activate_dataset(action_config, context, db: Database = None):
    with db as session:
        ds = session.query(orm.Dataset).filter_by(id=context["dataset_id"]).first()
        if not ds:
            return ItemResult.FAILURE
        ds.status = "ACTIVE"
        session.commit()
        return ItemResult.SUCCESS


@injector.inject
def flag_dataset_for_review(action_config, context, db: Database = None):
    with db as session:
        ds = session.query(orm.Dataset).filter_by(id=context["dataset_id"]).first()
        if not ds:
            return ItemResult.FAILURE
        ds.status = "UNDER_REVIEW"
        session.commit()
        return ItemResult.SUCCESS
