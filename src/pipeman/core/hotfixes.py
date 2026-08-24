"""
These are one-off hotfixes that needed to be coded. Don't apply them unless you know what
you're doing
"""
import click
import typing as t
from autoinject import injector

from pipeman.entity.entity_field import ComponentReferenceField, InlineEntityField, InlineEntityReferenceField, \
    EntityReferenceField

hotfix_map: dict[str, t.Callable] = {}

def _hotfix_glider_gzip_suffix():
    from pipeman.dataset import DatasetController
    from pipeman.entity import EntityController
    import pipeman.db.orm as orm

    @injector.inject
    def _call_me(dc: DatasetController = None, ec: EntityController = None):
        with dc.db as session:
            q = session.query(orm.Dataset).filter(orm.Dataset.is_deprecated == False)
            for dataset in q.all():
                ds_data = dataset.latest_published_revision()
                if ds_data is not None:
                    ds = dc.load_dataset(dataset.id, ds_data.revision_no, session)
                    distributors: ComponentReferenceField = ds.get_field("distributors")
                    for distributor in distributors.data():
                        if distributor.guid == "distribute_openglider":
                            web_link_field: InlineEntityReferenceField = distributor.get_field("primary_web_link")
                            web_link = web_link_field.value
                            if not isinstance(web_link, dict):
                                raise TypeError("expecting dict")
                            if "url" not in web_link:
                                raise ValueError("missing url key")
                            if web_link["url"]["und"].endswith(".gz.gz"):
                                web_link["url"]["und"] = web_link["url"]["und"][:-3]
                            elif not web_link["url"]["und"].endswith(".gz"):
                                web_link["url"]["und"] = web_link["url"]["und"] + ".gz"
                            else:
                                continue
                            ec.save_entity(distributor, session)
                            print(f"updated entity {distributor.container_id} for {dataset.id}")
    _call_me()


def _hotfix_glider_sensor_serials():
    # old sensor element ID -> new sensor element ID
    serial_no_replacements: dict[int, int] = {
        13850: 13902,
        22012: 14778,
        14107: 14009,
        14402: 14351,
        22060: 19151,
        17284: 16608,
        16281: 16042,
        18292: 16092,
        17920: 19149,
        18293: 17068,
        17921: 19150,
        17285: 16328,
        16282: 16093,
        14106: 14008,
        14401: 14350,
        15724: 14687,
        22010: 13901,
        13848: 13901,
        17922: 19151,
    }
    from pipeman.dataset import DatasetController
    import pipeman.db.orm as orm

    @injector.inject
    def _call_me(dc: DatasetController = None):
        with dc.db as session:
            q = session.query(orm.Dataset).filter(orm.Dataset.is_deprecated == False)
            for dataset in q.all():
                ds_data = dataset.latest_published_revision()
                if ds_data is not None:
                    ds = dc.load_dataset(dataset.id, ds_data.revision_no)
                    instruments: EntityReferenceField = ds.get_field("instruments")
                    if instruments is None or instruments.value is None:
                        print("no value for instruments")
                        continue
                    if not isinstance(instruments.value, list):
                        raise TypeError("expecting list")
                    if not any(x in instruments.value or str(x) in instruments.value for x in serial_no_replacements):
                        print("no replacements found")
                        continue
                    new_value = []
                    for instrument_id in instruments.value:
                        if isinstance(instrument_id, str) and instrument_id.isdigit():
                            instrument_id = int(instrument_id)
                        if instrument_id in serial_no_replacements:
                            new_value.append(serial_no_replacements[int(instrument_id)])
                        else:
                            new_value.append(instrument_id)
                    instruments.value = new_value
                    dc.save_metadata(ds)
                    dc.publish_dataset(dc.load_dataset(dataset.id), False, True)
                    print(f"republished {dataset.id}")
    _call_me()


hotfix_map["glider_zero_serials"] = _hotfix_glider_sensor_serials
hotfix_map["glider_gzip_filenames"] = _hotfix_glider_gzip_suffix


@click.command
@click.argument("hotfix_name")
def hotfix(hotfix_name: str):
    if hotfix_name not in hotfix_map:
        print(f"No hotfix named {hotfix_name}")
        exit(1)
    user_in = input(f"Are you sure you want to apply hotfix {hotfix_name} [y/n]: ")
    if user_in.lower() == "y":
        hotfix_map[hotfix_name]()
        print("Complete")
        exit(0)
    else:
        print("Cancelled")
        exit(1)


