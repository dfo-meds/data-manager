from autoinject import injector
from pipeman.db import Database
import pipeman.db.orm as orm
from pipeman.util.errors import DatasetNotFoundError
from .dataset import MetadataRegistry
import json
import datetime
from sqlalchemy.exc import IntegrityError


@injector.injectable
class DatasetController:

    db: Database = None
    reg: MetadataRegistry = None

    @injector.construct
    def __init__(self):
        pass

    def load_dataset(self, dataset_id, revision_no=None):
        with self.db as session:
            ds = session.query(orm.Dataset).filter_by(id=dataset_id).first()
            if not ds:
                raise DatasetNotFoundError(dataset_id)
            ds_data = ds.latest_revision() if revision_no is None else ds.specific_revision(revision_no)
            return self.reg.build_dataset(
                ds.profiles.replace("\r", "").split("\n"),
                json.loads(ds_data.data) if ds_data else {},
                ds.id,
                ds_data.id if ds_data else None,
                json.loads(ds.display_names) if ds.display_names else None
            )

    def save_dataset(self, dataset):
        with self.db as session:
            ds = None
            if dataset.dataset_id:
                ds = session.query(orm.Dataset).filter_by(id=dataset.dataset_id).first()
                if not ds:
                    raise DatasetNotFoundError(dataset.dataset_id)
                ds.modified_date = datetime.datetime.now()
                ds.is_deprecated = dataset.is_deprecated
                ds.display_names = json.dumps(dataset.get_displays())
                ds.profiles = "\n".join(dataset.profiles)
            else:
                ds = orm.Dataset(
                    created_date=datetime.datetime.now(),
                    modified_date=datetime.datetime.now(),
                    is_deprecated=False,
                    display_names=json.dumps(dataset.get_displays()),
                    profiles="\n".join(dataset.profiles)
                )
                session.add(ds)
            session.commit()
            dataset.dataset_id = ds.id
            retries = 5
            while retries > 0:
                retries -= 1
                try:
                    rev_nos = [dd.revision_no for dd in ds.data]
                    next_rev = 1 if not rev_nos else max(rev_nos) + 1
                    ds_data = orm.DatasetData(
                        dataset_id=ds.id,
                        revision_no=next_rev,
                        data=json.dump(dataset.values()),
                        created_date=datetime.datetime.now()
                    )
                    session.add(ds_data)
                    session.commit()
                    break
                except IntegrityError:
                    continue
