import flask_login
import flask
import pipeman.util.flask
import flask_wtf.file as fwf
import json
import pipeman.db.orm as orm
import datetime
import sqlalchemy as sa
import wtforms as wtf
import time
import zirconium as zr
import logging
import markupsafe
import asyncio
from pipeman.attachment import AttachmentController
from pipeman.util.flask import ActionList, flasht
from pipeman.util.errors import WorkflowNotFoundError
from autoinject import injector
from pipeman.db import Database
from pipeman.i18n import MultiLanguageString
from pipeman.i18n import gettext, format_datetime, DelayedTranslationString
from pipeman.util.flask import DataQuery, DataTable, DatabaseColumn, CustomDisplayColumn, ActionListColumn
from flask_wtf.file import FileField
from .workflow import WorkflowRegistry
from .steps import ItemResult, StepStatus, ItemNextAction
from pipeman.util.cron import CronThread, UniqueTaskThreadManager
import functools


class ItemDisplayWrapper:
    reg: WorkflowRegistry = None

    @injector.construct
    def __init__(self, workflow_item):
        self.item = workflow_item

    def __getattr__(self, item):
        return getattr(self.item, item)

    def object_link(self):
        if self.item.workflow_type.startswith('dataset_'):
            return flask.url_for('core.view_dataset', dataset_id=self.item.object_id)
        return ""

    @injector.inject
    def object_link_text(self, db: Database = None):
        with db as session:
            if self.item.workflow_type.startswith('dataset_'):
                obj = session.query(orm.Dataset).filter_by(id=self.item.object_id).first()
                if obj:
                    return MultiLanguageString(json.loads(obj.display_names) if obj.display_names else {})
        return ""

    def properties(self):
        return [
            (gettext('pipeman.label.witem.object_link'),
             markupsafe.Markup(f"<a href='{self.object_link()}'>{self.object_link_text()}</a>")),
            (gettext('pipeman.label.witem.type'), gettext(f'pipeman.label.witem.type.{self.item.workflow_type}')),
            (gettext('pipeman.label.witem.name'),
             self.reg.workflow_display(self.item.workflow_type, self.item.workflow_name)),
            (gettext('pipeman.label.witem.created'), format_datetime(self.item.created_date)),
            (gettext('pipeman.label.witem.status'), gettext(f'pipeman.label.witem.status.{self.item.status.lower()}')),
        ]

    def steps(self):
        decision_list = {}
        for decision in self.item.decisions:
            decision_list[decision.step_name] = decision
        step_list = json.loads(self.item.step_list)
        outputs = json.loads(self.item.step_output) if self.item.step_output else {}
        ctx = json.loads(self.item.context) if self.item.context else {}
        skip_info = (None, None) if '_final_completed_step' not in ctx else (
        ctx['_final_completed_step'], ctx['_first_cleanup_step'])
        current_step_state = StepStatus.interpret_status(self.item.status)
        for idx, step in enumerate(step_list):
            data = [self.reg.step_display(step)]
            info = []
            if str(idx) in outputs:
                info.extend(outputs[str(idx)])
            if step in decision_list:
                template = gettext("pipeman.label.witem.step.gate_completed") if decision_list[
                    step].decision else gettext("pipeman.label.witem.step.gate_cancelled")
                template = template.format(
                    decider=decision_list[step].decider_id,
                    date=format_datetime(decision_list[step].decision_date)
                )
                info.append(template)
                if decision_list[step].comments:
                    info.append(
                        str(gettext('pipeman.label.witem.step.comments')) + ": " + str(decision_list[step].comments))
                if decision_list[step].attachment_id:
                    att = decision_list[step].attachment
                    link = flask.url_for('core.view_attachment', attachment_id=att.id)
                    info.append(markupsafe.Markup(
                        f'{gettext("pipeman.label.witem.step.attachment")}: <a href="{link}">{markupsafe.escape(att.file_name)}</a>'))
            clean_info = [markupsafe.escape(x) for x in info]
            data.append(markupsafe.Markup('<br />'.join(clean_info)))
            if skip_info[0] and skip_info[1] and skip_info[0] < idx < (skip_info[1] - 1):
                data.append('skipped')
            elif self.item.completed_index is None and idx == 0:
                data.append(current_step_state)
            elif self.item.completed_index > idx:
                data.append("complete")
            elif self.item.completed_index == idx:
                data.append(current_step_state)
            else:
                data.append("pending")
            yield data


@injector.injectable
class WorkflowController:

    db: Database = None
    reg: WorkflowRegistry = None
    cfg: zr.ApplicationConfig = None
    attachments: AttachmentController = None

    @injector.construct
    def __init__(self):
        self._log = logging.getLogger("pipeman.workflow")

    def start_workflow(self, workflow_type, workflow_name, workflow_context, object_id=None, object_type="dataset"):
        with self.db as session:
            item = orm.WorkflowItem(
                workflow_type=workflow_type,
                workflow_name=workflow_name,
                object_id=object_id,
                object_type=object_type,
                context=json.dumps(workflow_context),
                step_list=json.dumps(self.reg.step_list(workflow_type, workflow_name)),
                created_date=datetime.datetime.now(),
                created_by=flask_login.current_user.user_id,
                completed_index=0,
                status="IN_PROGRESS"
            )
            session.add(item)
            session.commit()
            self._start_next_step(item, session)
            return item.status, item.id

    def check_exists(self, workflow_type, workflow_name, context_filters=None, object_id=None, object_type="dataset"):
        with self.db as session:
            for item in session.query(orm.WorkflowItem).filter_by(
                    workflow_type=workflow_type,
                    workflow_name=workflow_name,
                    object_id=object_id,
                    object_type=object_type
            ).filter(orm.WorkflowItem.status.notin_(('FAILURE', 'CANCELLED', 'COMPLETE'))):
                if context_filters is None:
                    return True
                else:
                    ctx = json.loads(item.context) if item.context else {}
                    for x in context_filters:
                        if x not in ctx or not ctx[x] == context_filters[x]:
                            break
                    else:
                        return True
        return False

    def workflow_item_status_by_id(self, item_id):
        with self.db as session:
            item = session.query(orm.WorkflowItem).filter_by(id=item_id).first()
            if not item:
                return "unknown"
            return StepStatus.interpret_status(item.status)

    def workflow_item_statuses_by_object_id(self, workflow_type, object_id):
        with self.db as session:
            return [
                StepStatus.interpret_status(item.status)
                for item in session.query(orm.WorkflowItem).filter_by(object_id=object_id, workflow_type=workflow_type)
            ]

    def workflow_form(self, item_id, decision: bool = True):
        with self.db as session:
            item = session.query(orm.WorkflowItem).filter_by(id=item_id).first()
            if not item:
                return flask.abort(404)
            if not self._has_access(item, "decide"):
                return flask.abort(403)
            item_url = flask.url_for("core.view_item", item_id=item_id)
            base_key = "pipeman.workflow.page.continue" if decision else 'pipeman.workflow.page.cancel'
            form = WorkflowItemForm()
            if form.validate_on_submit():
                if self._make_decision(item, session, decision, form):
                    flasht(f"{base_key}.success", "success")
                return flask.redirect(item_url)
            return flask.render_template(
                "form.html",
                form=form,
                instructions=gettext(f"{base_key}.instructions"),
                title=gettext(f"{base_key}.title"),
                back=item_url
            )
        # gettext('pipeman.workflow.page.continue.title')
        # gettext('pipeman.workflow.page.continue.instructions')
        # gettext('pipeman.workflow.page.continue.success')
        # gettext('pipeman.workflow.page.cancel.title')
        # gettext('pipeman.workflow.page.cancel.instructions')
        # gettext('pipeman.workflow.page.cancel.success')

    def view_item_page(self, item_id):
        with self.db as session:
            item = session.query(orm.WorkflowItem).filter_by(id=item_id).first()
            if not item:
                return flask.abort(404)
            if not self._has_access(item, "view"):
                return flask.abort(403)
            actions = self._build_action_list(item, False)
            return flask.render_template(
                "view_workflow_item.html",
                item=ItemDisplayWrapper(item),
                title=gettext("pipeman.workflow.page.view_item.title"),
                actions=actions
            )

    def list_workflow_items_page(self, active_only: bool = True):
        return flask.render_template(
            "data_table.html",
            table=self._item_table(active_only),
            title=gettext("pipeman.workflow.page.list_items.title")
        )

    def list_workflow_items_ajax(self, active_only: bool = True):
        return self._item_table(active_only).ajax_response()

    def _format_workflow_type(self, data_row):
        return gettext(f'pipeman.label.witem.type.{data_row.workflow_type}')

    def _format_workflow_name(self, data_row):
        return self.reg.workflow_display(data_row.workflow_type, data_row.workflow_name)

    def _format_object_link(self, data_row):
        obj_link = None
        obj_name = str(data_row.object_id)
        if data_row.workflow_type.startswith("dataset") or data_row.object_type == 'dataset':
            with self.db as session:
                obj = session.query(orm.Dataset).filter_by(id=data_row.object_id).first()
                if obj:
                    obj_name = MultiLanguageString(
                        json.loads(obj.display_names)
                        if obj.display_names else
                        {"und": data_row.object_id}
                    )
                    obj_link = flask.url_for('core.view_dataset', dataset_id=data_row.object_id)
        if obj_link:
            return markupsafe.Markup(f"<a href='{obj_link}'>{obj_name}</a>")
        return obj_name

    def _format_workflow_status(self, data_row):
        return gettext(f'pipeman.label.witem.status.{data_row.status.lower()}')

    def object_link(self):
        if self.item.object_type == 'dataset':
            return flask.url_for('core.view_dataset', dataset_id=self.item.object_id)
        return ""

    @injector.inject
    def object_link_text(self, db: Database = None):
        with db as session:
            if self.item.object_type == 'dataset':
                obj = session.query(orm.Dataset).filter_by(id=self.item.object_id).first()
                if obj:
                    return MultiLanguageString(json.loads(obj.display_names) if obj.display_names else {})
        return ""

    def _item_table(self, active_only: bool = True):
        filters = []
        if active_only:
            filters.append(orm.WorkflowItem.status == 'DECISION_REQUIRED')
        dq = DataQuery(orm.WorkflowItem, extra_filters=filters)
        dt = DataTable(
            table_id="action_list",
            base_query=dq,
            ajax_route=flask.url_for("core.list_items_ajax", active_only=(1 if active_only else 0)),
            default_order=[("created_date", "asc")]
        )
        dt.add_column(DatabaseColumn(
            "id",
            gettext("pipeman.label.witem.id"),
            allow_order=True
        ))
        dt.add_column(CustomDisplayColumn(
            "workflow_type",
            gettext("pipeman.label.witem.workflow_type"),
            self._format_workflow_type
        ))
        dt.add_column(CustomDisplayColumn(
            "workflow_name",
            gettext("pipeman.label.witem.workflow_name"),
            self._format_workflow_name
        ))
        dt.add_column(CustomDisplayColumn(
            "status",
            gettext("pipeman.label.witem.status"),
            self._format_workflow_status
        ))
        dt.add_column(DatabaseColumn(
            "created_date",
            gettext("pipeman.label.witem.created"),
            allow_order=True,
            formatter=format_datetime
        ))
        dt.add_column(CustomDisplayColumn(
            "object_link",
            gettext("pipeman.label.witem.object_link"),
            self._format_object_link
        ))
        dt.add_column(ActionListColumn(
            action_callback=self._build_action_list
        ))
        return dt

    def _build_action_list(self, item, short_mode: bool = True):
        actions = ActionList()
        kwargs = {'item_id': item.id}
        if short_mode:
            actions.add_action('pipeman.workflow.page.view_item.link', 'core.view_item', **kwargs)
        if self._has_access(item, 'decide'):
            actions.add_action('pipeman.workflow.page.continue.link', 'core.approve_item', **kwargs)
            actions.add_action('pipeman.workflow.page.cancel.link', 'core.cancel_item', **kwargs)
        #if self._has_access(item, 'restart'):
            #actions.add_action('pipeman.workflow.page.restart.link', 'core.restart_item', **kwargs)
        return actions

    def _item_query(self, session, only_active: bool = True):
        query = session.query(orm.WorkflowItem)
        if only_active:
            query = query.filter_by(status='DECISION_REQUIRED')
        return query

    def _iterate_workflow_items(self, items):
        for item in items:
            if not self._has_access(item, 'view'):
                continue
            yield ItemDisplayWrapper(item), self._build_action_list(item, True)

    def _has_access(self, item, mode, log_access_failure: bool = False):
        step, steps = self._build_next_step(item)
        if step is None:
            if mode == 'view':
                if flask_login.current_user.has_permission('action_items.view.completed_steps'):
                    return True
                if log_access_failure:
                    self._log.warning(f"Access to view completed item denied, missing action_items.view.completed_steps")
                return False
            if log_access_failure:
                self._log.warning(f"Cannot make decisions for completed items")
            return False
        ctx = json.loads(item.context)
        if mode == 'view':
            if step.allow_view(ctx):
                return True
            else:
                if log_access_failure:
                    self._log.warning(f"View access to {item.id} denied")
                return False
        elif mode == 'decide':
            if step.allow_decision(ctx):
                return True
            else:
                if log_access_failure:
                    self._log.warning(f"Decision access to {item.id} denied")
                return False
        else:
            if log_access_failure:
                self._log.warning(f"Unrecognized acces mode {mode}")
        return False

    def cleanup_old_items(self, st = None):
        # TODO: add old item removal for completed workflow items
        #self._log.info(f"Cleaning up old workflow items")
        self._log.warning(f"Cleanup not implemented")

    async def async_batch_process_items(self, st = None):
        self._log.info(f"Starting async batch jobs")
        max_exec_time = 1000000000 * self.cfg.as_int(("pipeman", "async_batch_process_time"), default=5)
        max_items = self.cfg.as_int(("pipeman", "async_max_items"), default=5)
        with self.db as session:
            q = sa.update(orm.WorkflowItem).where(orm.WorkflowItem.status == 'ASYNC_DELAY').values({
                'status': 'ASYNC_EXECUTE'
            })
            session.execute(q)
            session.commit()
            start_time = time.monotonic_ns()
            cont = True
            tasks = []
            while cont:
                cont = False
                for item in session.query(orm.WorkflowItem).filter_by(status="ASYNC_EXECUTE"):
                    cont = True
                    if st.halt.is_set() or (time.monotonic_ns() - start_time) > max_exec_time:
                        cont = False
                        break
                    tasks.append(asyncio.create_task(self._async_batch_execute(item, session)))
                    while len(tasks) >= max_items:
                        await asyncio.sleep(0.5)
                        if (st and st.halt.is_set()) or (time.monotonic_ns() - start_time) > max_exec_time:
                            cont = False
                            break
                        tasks, _ = await asyncio.wait(tasks)
            await asyncio.gather(*tasks)

    async def _async_batch_execute(self, item, session):
        step, steps = self._build_next_step(item)
        if step is None:
            session.commit()
            return
        ctx = self._build_context(item)
        result = await step.async_execute(ctx)
        self._handle_step_result(step, result, item, session, steps, ctx)

    def _handle_step_result(self, step, result, item, session, steps, ctx, st = None):
        if step.output:
            outputs = json.loads(item.step_output) if item.step_output else {}
            if str(item.completed_index) in outputs:
                outputs[str(item.completed_index)].extend([str(x) for x in step.output])
            else:
                outputs[str(item.completed_index)] = [str(x) for x in step.output]
            item.step_output = json.dumps(outputs)
        item_status, next_step = ItemResult.get_item_status_after_step(result)
        item.status = item_status.value
        if next_step == ItemNextAction.CONTINUE:
            item.completed_index += 1
            item.context = json.dumps(ctx)
            session.commit()
            if st is None or not st.halt.is_set():
                self._start_next_step(item, session, steps, ctx)
        elif next_step == ItemNextAction.FAILURE:
            item.context = json.dumps(ctx)
            session.commit()
            self._handle_cleanup(item, session, steps, ctx, item.status, st=st)
        else:
            item.context = json.dumps(ctx)
            session.commit()

    def _handle_cleanup(self, item, session, steps, ctx, end_state, st = None):
        if '_in_cleanup' in ctx and ctx['_in_cleanup'] and (st is None or not st.halt.is_set()):
            self._start_next_step(item, session, steps, ctx)
            return
        cleanup_steps = None
        try:
            cleanup_steps = self.reg.cleanup_step_list(item.workflow_type, item.workflow_name)
        except WorkflowNotFoundError as ex:
            return
        if not cleanup_steps:
            return
        next_index = len(steps)
        steps.extend(cleanup_steps)
        # Remember the original state so we can set it when we finish
        ctx['_final_completed_step'] = item.completed_index
        ctx['_first_cleanup_step'] = next_index + 1
        ctx['_cleanup_set_state'] = end_state
        ctx['_in_cleanup'] = True
        item.step_list = json.dumps(steps)
        item.completed_index = next_index
        item.context = json.dumps(ctx)
        session.commit()
        if st is None or not st.halt.is_set():
            self._start_next_step(item, session, steps, ctx)

    def _build_next_step(self, item, steps=None, ctx=None):
        steps = steps or json.loads(item.step_list)
        next_index = item.completed_index
        if next_index >= len(steps):
            ctx = self._build_context(item, ctx)
            if '_cleanup_set_state' in ctx and ctx['_cleanup_set_state']:
                item.status = ctx['_cleanup_set_state']
            else:
                item.status = StepStatus.COMPLETED.value
            return None, None
        step = self.reg.construct_step(steps[next_index])
        step.set_item(item)
        return step, steps

    def _start_next_step(self, item, session, steps=None, ctx=None):
        step, steps = self._build_next_step(item, steps, ctx)
        if step is None:
            session.commit()
            return
        ctx = self._build_context(item, ctx)
        result = step.execute(ctx)
        self._handle_step_result(step, result, item, session, steps, ctx)

    def batch_process(self, st, item_id):
        with self.db as session:
            item = session.query(orm.WorkflowItem).filter_by(id=item_id).first()
            if not item:
                self._log.warning(f"Item ID {item_id} requested but not found")
                return
            step, steps = self._build_next_step(item)
            if step is None:
                session.commit()
                return
            ctx = self._build_context(item)
            result = step.batch(ctx)
            self._handle_step_result(step, result, item, session, steps, ctx, st=st)
            item.locked_since = None
            session.commit()

    def _make_decision(self, item, session, decision: bool, form=None):
        step, steps = self._build_next_step(item)
        if step is None:
            session.commit()
            return
        att_id = None
        if form.file_submission.data:
            att_id = self.attachments.create_attachment(
                form.file_submission.data,
                f"witem{item.id}",
                item.object_id if item.workflow_type.startswith("dataset") else None,
                form.file_name.data
            )
            if att_id is None:
                flasht("pipeman.workflow.error.file_upload_error", "error")
                return False
        dec = orm.WorkflowDecision(
            workflow_item_id=item.id,
            step_name=step.step_name,
            decider_id=flask_login.current_user.get_id(),
            decision=decision,
            decision_date=datetime.datetime.now(),
            comments=form.comments.data if form else "",
            attachment_id=att_id
        )
        session.add(dec)
        ctx = self._build_context(item)
        result = step.complete(decision, ctx)
        self._handle_step_result(step, result, item, session, steps, ctx)
        session.commit()
        return True

    def _build_context(self, item, ctx=None):
        if ctx is None:
            ctx = json.loads(item.context) if item.context else {}
        ctx['_id'] = item.id
        return ctx


class WorkflowItemForm(pipeman.util.flask.PipemanFlaskForm):
    comments = wtf.TextAreaField(
        DelayedTranslationString("pipeman.label.witem.step.comments")
    )

    file_name = wtf.StringField(
        DelayedTranslationString("pipeman.label.witem.step.approval_file.name")
    )

    file_submission = FileField(
        DelayedTranslationString("pipeman.label.witem.step.approval_file"),
        validators=[
            fwf.FileAllowed(["pdf", "jpg", "png"])
        ]
    )

    submit = wtf.SubmitField(
        DelayedTranslationString("pipeman.common.submit")
    )

    def __init__(self):
        super().__init__()


class WorkflowCronThread(CronThread):

    db: Database = None
    cfg: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self, app):
        super().__init__(app)
        self._sleep_interval = self.cfg.as_float(("pipeman", "workflow", "task_thread_sleep_seconds"), default=5)
        self._reset_interval = self.cfg.as_float(("pipeman", "workflow", "task_thread_reset_sleep_seconds"), default=300)
        self._max_threads = self.cfg.as_int(("pipeman", "workflow", "max_sub_threads"), default=5)
        self._lock_time = self.cfg.as_float(("pipeman", "workflow", "task_lock_time_minutes"), default=30)  # minutes
        self._finish_delay_time = self.cfg.as_float(("pipeman", "workflow", "max_exit_delay_time_seconds"), default=5)
        self._last_reset = None
        self._tasks = UniqueTaskThreadManager(app, self.halt, self._max_threads)

    def _run(self):
        while not self.halt.is_set():
            if self._last_reset is None or (time.monotonic() - self._last_reset) > self._reset_interval:
                self._reset_delayed_jobs()
            self._check_for_jobs()
            self._tasks.sow()
            self.halt.wait(self._sleep_interval)
        self._tasks.wait_for_all(self._finish_delay_time)

    def _check_for_jobs(self):
        with self.db as session:
            for item in session.query(orm.WorkflowItem).filter_by(status="BATCH_EXECUTE"):
                if self.halt.is_set():
                    break
                item.status = "BATCH_IN_PROGRESS"
                item.locked_since = datetime.datetime.now()
                session.commit()
                self._tasks.execute(f'workflow_item{item.id}',
                                    functools.partial(self._handle_batch_job, item_id=item.id))

    @injector.inject
    def _handle_batch_job(self, st, item_id, wc: WorkflowController=None):
        wc.batch_process(st, item_id)

    def _reset_delayed_jobs(self):
        with self.db as session:
            q = sa.update(orm.WorkflowItem).where(orm.WorkflowItem.status == 'BATCH_DELAY').values({
                'status': 'BATCH_EXECUTE'
            })
            session.execute(q)
            session.commit()
            if self.halt.is_set():
                return
            gate = datetime.datetime.now() - datetime.timedelta(minutes=self._lock_time)
            q = (
                    sa.update(orm.WorkflowItem)
                    .where(orm.WorkflowItem.status == 'BATCH_IN_PROGRESS')
                    .where(orm.WorkflowItem.locked_since < gate)
                    .values({'status': 'BATCH_EXECUTE', 'locked_since': None})
            )
            session.execute(q)
            session.commit()
