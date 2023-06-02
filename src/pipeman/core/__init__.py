from autoinject import injector
from pipeman.util import caps_to_snake
from pipeman.util import System
from pipeman.db import Database
import pipeman.db.orm as orm
import sqlalchemy as sa
import datetime
import zirconium as zr
import zrlog
from pipeman.entity import EntityRegistry
from pipeman.dataset import MetadataRegistry
from pipeman.vocab import VocabularyRegistry
from pipeman.workflow import WorkflowRegistry


@injector.inject
def init(system):
    system.register_cli("pipeman.core.cli", "org")
    system.register_cli("pipeman.core.cli", "workflow")
    system.register_cli("pipeman.core.cli", "report")
    system.register_cli("pipeman.core.cli", "core")
    system.register_blueprint("pipeman.core.app", "base")
    system.register_blueprint("pipeman.core.app", "core")
    system.on_app_init(core_init_app)
    system.on_cleanup(_do_cleanup)
    system.on_cron_start(_register_cron)
    system.pre_setup(_reset_registries)


def _register_cron(cron):
    cron.register_periodic_job("cleanup_datasets", _do_cleanup, days=7)


@injector.inject
def _do_cleanup(st = None, db: Database = None, cfg: zr.ApplicationConfig = None):
    def _chunks(iter, size=1000):
        i = 0
        m = len(iter)
        while i < m:
            yield iter[i:i+size]
            i += size

    with db as session:

        # Handle entity data pruning
        keep_entity_days = cfg.as_int(("pipeman", "retain_entity_revisions_days"), default=365)
        if keep_entity_days > 0:
            zrlog.get_logger("pipeman.entity").notice(f"Pruning unused entity versions older than {keep_entity_days}")
            dt = datetime.datetime.now() - datetime.timedelta(days=keep_entity_days)
            remove_revisions = []
            for ent in session.query(orm.Entity):
                latest_rev = ent.latest_revision()
                for rev in ent.data:
                    if latest_rev.revision_no == rev.revision_no:
                        continue
                    if rev.modified_date >= dt:
                        continue
                    remove_revisions.append(rev.id)
                if st and st.halt.is_set():
                    break
            for chunk in _chunks(remove_revisions):
                if st and st.halt.is_set():
                    break
                q = sa.delete(orm.EntityData).where(orm.EntityData.id.in_(chunk))
                session.execute(q)
                session.commit()

        # Handle dataset pruning
        keep_dataset_days = cfg.as_int(("pipeman", "retain_unpub_dataset_revisions_days"), default=365)
        keep_old_pub_dataset_days = cfg.as_int(("pipeman", "retain_oldpub_dataset_revisions_days"), default=-1)
        if keep_dataset_days > 0 or keep_old_pub_dataset_days > 0:
            zrlog.get_logger("pipeman.dataset").notice(f"Pruning unused dataset versions older than {keep_dataset_days} and previous published datasets older than {keep_old_pub_dataset_days}")
            unpub_gate = None if keep_dataset_days < 0 else datetime.datetime.now() - datetime.timedelta(days=keep_dataset_days)
            oldpub_gate = None if keep_old_pub_dataset_days < 0 else datetime.datetime.now() - datetime.timedelta(days=keep_old_pub_dataset_days)
            remove_dataset_editions = []
            remove_workflow_items = []
            remove_attachments = []
            for ds in session.query(orm.Dataset):
                latest_rev = ds.latest_revision()
                latest_pub_rev = ds.latest_published_revision()
                for rev in ds.data:
                    if latest_rev.revision_no == rev.revision_no:
                        continue
                    if latest_pub_rev and latest_pub_rev.revision_no == rev.revision_no:
                        continue
                    if rev.is_published and (oldpub_gate is None or rev.modified_date >= oldpub_gate):
                        continue
                    if (not rev.is_published) and (unpub_gate is None or rev.modified_date >= unpub_gate):
                        continue
                    if rev.approval_item_id:
                        remove_workflow_items.append(rev.approval_item_id)
                        for decision in rev.approval_item.decisions:
                            if decision.attachment_id:
                                remove_attachments.append(decision.attachment_id)
                    remove_dataset_editions.append(rev.id)
                if st and st.halt.is_set():
                    break
            for chunk in _chunks(remove_dataset_editions, 1000):
                if st and st.halt.is_set():
                    break
                q = sa.delete(orm.MetadataEdition).where(orm.MetadataEdition.id.in_(chunk))
                session.execute(q)
                session.commit()
            for chunk in _chunks(remove_attachments, 1000):
                if st and st.halt.is_set():
                    break
                q = sa.delete(orm.Attachment).where(orm.Attachment.id.in_(chunk))
                session.execute(q)
                session.commit()
            for chunk in _chunks(remove_workflow_items, 1000):
                if st and st.halt.is_set():
                    break
                q = sa.delete(orm.WorkflowDecision).where(orm.WorkflowDecision.workflow_item_id.in_(chunk))
                session.execute(q)
                q = sa.delete(orm.WorkflowItem).where(orm.WorkflowItem.id.in_(chunk))
                session.execute(q)
                session.commit()


@injector.inject
def _reset_registries(mreg: MetadataRegistry = None, ereg: EntityRegistry = None, vreg: VocabularyRegistry = None, wreg: WorkflowRegistry = None):
    mreg.remove_all()
    ereg.remove_all()
    vreg.remove_all()
    wreg.remove_all()


@injector.inject
def core_init_app(app, system: System = None):
    system.register_nav_item("datasets", "pipeman.datasets", "core.list_datasets", "datasets.view")
    system.register_nav_item("entities", "pipeman.entities", "core.list_entities", "entities.view")
    system.register_nav_item("action-items", "pipeman.action-items", "core.list_workflow_items", "action_items.view")
    system.register_nav_item("action-history", "pipeman.action-history", "core.list_workflow_history", "action_items.history")
    system.register_nav_item("organizations", "pipeman.organizations", "core.list_organizations", "organizations.view")
    system.register_nav_item("vocabularies", "pipeman.vocabularies", "core.list_vocabularies", "vocabularies.view")
    system.register_nav_item("home", "pipeman.home", "base.home", "_is_not_anonymous", "user", weight=-500)
    system.register_nav_item("logout", "pipeman.menu.logout", "auth.logout", "_is_not_anonymous", "user", weight=10000)
    system.register_nav_item("login", "pipeman.menu.login", "auth.login", "_is_anonymous", "user", weight=10000)
    app.jinja_env.filters['caps_to_snake'] = caps_to_snake
