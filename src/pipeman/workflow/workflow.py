import uuid
from enum import Enum
import importlib
import flask_login
import flask
from pipeman.util.flask import ConfirmationForm, ActionList, flasht
from pipeman.util import deep_update
from pipeman.util.errors import StepNotFoundError, StepConfigurationError, WorkflowNotFoundError, WorkflowItemNotFoundError
from autoinject import injector
from pipeman.db import Database
from pipeman.i18n import MultiLanguageString
import json
import pipeman.db.orm as orm
import datetime
import sqlalchemy as sa
import requests
import wtforms as wtf
import time
import zirconium as zr
from pipeman.i18n import gettext, format_datetime, DelayedTranslationString
import logging
import markupsafe
from wtforms.form import BaseForm
from pipeman.entity import FieldContainer
import asyncio
from pipeman.util.flask import DataQuery, DataTable, DatabaseColumn, CustomDisplayColumn, ActionListColumn
from pipeman.db import BaseObjectRegistry
import yaml


class ItemResult(Enum):

    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    BATCH_EXECUTE = "batch_execute"
    ASYNC_EXECUTE = "async_execute"
    DECISION_REQUIRED = "decision_required"
    REMOTE_EXECUTE_REQUIRED = "remote_required"


@injector.injectable_global
class WorkflowRegistry:

    def __init__(self):
        self._steps = BaseObjectRegistry("step")
        self._workflows = BaseObjectRegistry("workflow")
        self._factories = []
        self._factories.append(DefaultStepFactory())

    def reload_types(self):
        self._steps.reload_types()
        self._workflows.reload_types()

    def register_step_factory(self, factory):
        self._factories.append(factory)

    def register_workflow(self, workflow_name, category, **config):
        self._workflows.register(f"{category}__{workflow_name}", **config)

    def register_step(self, step_name, **config):
        self._steps.register(step_name, **config)

    def register_steps_from_dict(self, d: dict):
        self._steps.register_from_dict(d)

    def register_steps_from_yaml(self, yaml_file):
        self._steps.register_from_yaml(yaml_file)

    def register_workflows_from_dict(self, d: dict):
        for cat_name in d or {}:
            for obj_name in d[cat_name] or {}:
                self.register_workflow(obj_name, cat_name, **d[cat_name][obj_name])

    def register_workflows_from_yaml(self, f):
        with open(f, "r", encoding="utf-8") as h:
            self.register_workflows_from_dict(yaml.safe_load(h))

    def step_display(self, step_name):
        return MultiLanguageString(self._steps[step_name]['label'] if step_name in self._steps else {"und": step_name})

    def workflow_display(self, category_name, workflow_name):
        key = f"{category_name}__{workflow_name}"
        return MultiLanguageString(self._workflows[key]['label'] if key in self._workflows else {"und": key})

    def construct_step(self, step_name):
        if step_name not in self._steps:
            raise StepNotFoundError(step_name)
        step_config = self._steps[step_name]
        for factory in self._factories:
            if factory.supports_step_type(step_config["step_type"]):
                return factory.build_step(step_name, step_config["step_type"], step_config)
        raise StepConfigurationError(f"Invalid step type for {step_name}: {step_config['step_type']}")

    def step_list(self, category_name, workflow_name):
        key = f"{category_name}__{workflow_name}"
        if key not in self._workflows:
            raise WorkflowNotFoundError(key)
        return self._workflows[key]["steps"]
        
    def cleanup_step_list(self, category_name, workflow_name):
        key = f"{category_name}__{workflow_name}"
        if key not in self._workflows:
            raise WorkflowNotFoundError(key)
        return self._workflows[key]["cleanup"] if "cleanup" in self._workflows[key] and self._workflows[key] else []

    def list_workflows(self, workflow_type):
        for key in self._workflows:
            if not key.startswith(f"{workflow_type}__"):
                continue
            if "enabled" in self._workflows[key] and not self._workflows[key]["enabled"]:
                continue
            yield key[len(workflow_type)+2:], MultiLanguageString(self._workflows[key]["label"] or {"und": key})


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
            (gettext('pipeman.label.witem.object_link'), markupsafe.Markup(f"<a href='{self.object_link()}'>{self.object_link_text()}</a>")),
            (gettext('pipeman.label.witem.type'), gettext(f'pipeman.label.witem.type.{self.item.workflow_type}')),
            (gettext('pipeman.label.witem.name'), self.reg.workflow_display(self.item.workflow_type, self.item.workflow_name)),
            (gettext('pipeman.label.witem.created'), format_datetime(self.item.created_date)),
            (gettext('pipeman.label.witem.status'), gettext(f'pipeman.label.witem.status.{self.item.status.lower()}')),
        ]

    def steps(self):
        decision_list = {}
        for decision in self.item.decisions:
            decision_list[decision.step_name] = decision
        step_list = json.loads(self.item.step_list)
        for idx, step in enumerate(step_list):
            data = [self.reg.step_display(step)]
            if step in decision_list:
                template = gettext("pipeman.label.witem.step.gate_completed") if decision_list[step].decision else gettext("pipeman.label.witem.step.gate_cancelled")
                template = template.format(
                    decider=decision_list[step].decider_id,
                    date=format_datetime(decision_list[step].decision_date)
                )
                data.append(template)
            else:
                data.append("")
            if self.item.completed_index is None and idx == 0:
                data.append("in-progress")
            elif self.item.completed_index > idx:
                data.append("complete")
            elif self.item.completed_index == idx:
                data.append("in-progress")
            else:
                data.append("pending")
            yield data
# gettext('pipeman.label.witem.step.in-progress')
# gettext('pipeman.label.witem.step.pending')
# gettext('pipeman.label.witem.step.complete')
# gettext('pipeman.label.witem.status.complete')
# gettext('pipeman.label.witem.status.failure')
# gettext('pipeman.label.witem.status.cancelled')
# gettext('pipeman.label.witem.status.in-progress')
# gettext('pipeman.label.witem.status.unknown')


@injector.injectable
class WorkflowController:

    db: Database = None
    reg: WorkflowRegistry = None
    cfg: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        pass

    def interpret_result(self, result):
        if result == ItemResult.SUCCESS:
            return "complete"
        elif result == ItemResult.FAILURE:
            return "failure"
        elif result == ItemResult.CANCELLED:
            return "cancelled"
        else:
            return "in-progress"

    def interpret_status(self, status):
        if status == "SUCCESS":
            return "complete"
        elif status == "FAILURE":
            return "failure"
        elif status == "CANCELLED":
            return "cancelled"
        else:
            return "in-progress"

    def start_workflow(self, workflow_type, workflow_name, workflow_context, object_id=None):
        with self.db as session:
            item = orm.WorkflowItem(
                workflow_type=workflow_type,
                workflow_name=workflow_name,
                object_id=object_id,
                context=json.dumps(workflow_context),
                step_list=json.dumps(self.reg.step_list(workflow_type, workflow_name)),
                created_date=datetime.datetime.now(),
                completed_index=0,
                status="IN_PROGRESS"
            )
            session.add(item)
            session.commit()
            self._start_next_step(item, session)
            return item.status, item.id

    def workflow_item_status_by_id(self, item_id):
        with self.db as session:
            item = session.query(orm.WorkflowItem).filter_by(id=item_id).first()
            if not item:
                return "unknown"
            return self.interpret_status(item.status)

    def workflow_item_statuses_by_object_id(self, workflow_type, object_id):
        with self.db as session:
            return [
                self.interpret_status(item.status)
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
            form = ConfirmationForm()
            if form.validate_on_submit():
                self._make_decision(item, session, decision)
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

    def _format_object_link(self, data_row):
        return data_row.object_id

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

    def _has_access(self, item, mode):
        step, steps = self._build_next_step(item)
        if step is None:
            return flask_login.current_user.has_permission("action_items.view.completed_steps") if mode == 'view' else False
        ctx = json.loads(item.context)
        if mode == 'view' and step.allow_view(ctx):
            return True
        elif mode == 'decide' and step.allow_decision(ctx):
            return True
        return False

    def batch_process_items(self):
        max_exec_time = 1000000000 * self.cfg.as_int(("pipeman", "batch_process_time"), default=5)
        with self.db as session:
            start_time = time.monotonic_ns()
            for item in session.query(orm.WorkflowItem).filter_by(status="BATCH_EXECUTE"):
                self._batch_execute(item, session)
                elapsed_time = time.monotonic_ns() - start_time
                if elapsed_time >= max_exec_time:
                    break

    async def async_batch_process_items(self):
        max_exec_time = 1000000000 * self.cfg.as_int(("pipeman", "async_batch_process_time"), default=5)
        max_items = self.cfg.as_int(("pipeman", "async_max_items"), default=5)
        with self.db as session:
            start_time = time.monotonic_ns()
            tasks = []
            for item in session.query(orm.WorkflowItem).filter_by(status="ASYNC_EXECUTE"):
                if (time.monotonic_ns() - start_time) > max_exec_time:
                    break
                tasks.append(asyncio.create_task(self._async_batch_execute(item, session)))
                while len(tasks) >= max_items:
                    await asyncio.sleep(0.5)
                    if (time.monotonic_ns() - start_time) > max_exec_time:
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
        self._handle_step_result(result, item, session, steps, ctx)

    def _handle_step_result(self, result, item, session, steps, ctx):
        if result == ItemResult.FAILURE:
            item.status = "FAILURE"
            # "gettext('pipeman.label.witem.status.failure')"
        elif result == ItemResult.DECISION_REQUIRED:
            item.status = "DECISION_REQUIRED"
            # "gettext('pipeman.label.witem.status.decision_required')"
        elif result == ItemResult.BATCH_EXECUTE:
            item.status = "BATCH_EXECUTE"
            # "gettext('pipeman.label.witem.status.batch_execute')"
        elif result == ItemResult.ASYNC_EXECUTE:
            item.status = "ASYNC_EXECUTE"
            # "gettext('pipeman.label.witem.status.async_execute')"
        elif result == ItemResult.CANCELLED:
            item.status = "CANCELLED"
            # "gettext('pipeman.label.witem.status.cancelled')"
        elif result == ItemResult.REMOTE_EXECUTE_REQUIRED:
            item.status = "REMOTE_EXEC_QUEUED"
            # "gettext('pipeman.label.witem.status.remote_exec_queued')"
        else:
            item.completed_index += 1
            item.status = "IN_PROGRESS"
            # "gettext('pipeman.label.witem.status.in_progress')"
        item.context = json.dumps(ctx)
        session.commit()
        if item.status == "IN_PROGRESS":
            self._start_next_step(item, session, steps, ctx)
        elif item.status in ('FAILURE', 'CANCELLED'):
            self._handle_cleanup(item, session, steps, ctx, item.status)
            
    def _handle_cleanup(self, item, session, steps, ctx, end_state):
        cleanup_steps = []
        try:
            cleanup_steps = self.reg.cleanup_steps(item.workflow_type, item.workflow_name)
        except WorkflowNotFoundError as ex:
            return
        if not cleanup_steps:
            return
        next_index = len(steps)
        steps.extend(cleanup_steps)
        # Remember the original state so we can set it when we finish
        ctx['_cleanup_set_state'] = end_state
        item.step_list = json.dumps(steps)
        item.completed_index = len(steps)
        item.context = json.dumps(ctx)
        session.commit()
        self._start_next_step(item, session, steps, ctx)

    def _build_next_step(self, item, steps=None, ctx=None):
        steps = steps or json.loads(item.step_list)
        next_index = item.completed_index
        if next_index >= len(steps):
            ctx = self._build_context(item, ctx)
            if '_cleanup_set_state' in ctx and ctx['_cleanup_set_state']:
                item.status = ctx['_cleanup_set_state']
            else:
                item.status = "COMPLETE"
            # "gettext('pipeman.label.witem.status.complete')"
            return None, None
        return self.reg.construct_step(steps[next_index]), steps

    def _start_next_step(self, item, session, steps=None, ctx=None):
        step, steps = self._build_next_step(item, steps, ctx)
        if step is None:
            session.commit()
            return
        ctx = self._build_context(item, ctx)
        result = step.execute(ctx)
        self._handle_step_result(result, item, session, steps, ctx)

    def _batch_execute(self, item, session):
        step, steps = self._build_next_step(item)
        if step is None:
            session.commit()
            return
        ctx = self._build_context(item)
        result = step.batch(ctx)
        self._handle_step_result(result, item, session, steps, ctx)

    def _make_decision(self, item, session, decision: bool):
        step, steps = self._build_next_step(item)
        if step is None:
            session.commit()
            return
        ctx = self._build_context(item)
        result = step.complete(decision, ctx)
        self._handle_step_result(result, item, session, steps, ctx)
        dec = orm.WorkflowDecision(
            workflow_item_id=item.id,
            step_name=step.step_name,
            decider_id=flask_login.current_user.get_id(),
            decision=decision,
            decision_date=datetime.datetime.now()
        )
        session.add(dec)
        session.commit()

    def _build_context(self, item, ctx=None):
        if ctx is None:
            ctx = json.loads(item.context) if item.context else {}
        ctx['_id'] = item.id
        return ctx


class WorkflowStep:

    def __init__(self, step_name: str, item_config: dict):
        self.item_config = item_config
        self.step_name = step_name

    def execute(self, context: dict) -> ItemResult:
        return self._execute_wrapper(self._execute, context)

    def batch(self, context: dict) -> ItemResult:
        return ItemResult.SUCCESS

    def allow_view(self, context: dict) -> bool:
        if "access_check" in self.item_config:
            if self.item_config["access_check"] is True:
                return True
            elif self.item_config["access_check"] is False:
                return False
            else:
                return self._call_function(self.item_config["access_check"], context, 'view')
        return True

    def allow_decision(self, context: dict) -> bool:
        if "require_permission" in self.item_config:
            if not flask_login.current_user.has_permission(self.item_config["require_permission"]):
                return False
        if "access_check" in self.item_config:
            if self.item_config["access_check"] is True:
                return True
            elif self.item_config["access_check"] is False:
                return False
            return self._call_function(self.item_config["access_check"], context, 'decide')
        return False

    async def async_execute(self, context: dict) -> ItemResult:
        return ItemResult.SUCCESS

    def _execute_wrapper(self, call_me, *args, **kwargs) -> ItemResult:
        try:
            res = call_me(*args, **kwargs)
            if res is None or res is True:
                return ItemResult.SUCCESS
            if res is False:
                return ItemResult.FAILURE
            return res
        except Exception as ex:
            logging.getLogger("pipeman.workflow").exception(ex)
            return ItemResult.FAILURE

    def _execute(self, context: dict) -> ItemResult:
        return ItemResult.SUCCESS

    def _call_function(self, func_path, *args, **kwargs):
        mod_pos = func_path.rfind(".")
        module_name = func_path[0:mod_pos]
        func_name = func_path[mod_pos+1:]
        module = importlib.import_module(module_name)
        func = getattr(module, func_name)
        return func(self.item_config, *args, **kwargs)


class WorkflowActionStep(WorkflowStep):

    STEP_TYPE = "action"

    def _execute(self, context: dict) -> ItemResult:
        return self._call_function(self.item_config["action"], context)


class WorkflowDelayedStep(WorkflowStep):

    def __init__(self, *args, execute_response, **kwargs):
        self.execute_response = execute_response
        super().__init__(*args, **kwargs)

    def _execute(self, context: dict) -> ItemResult:
        if "pre_action" in self.item_config:
            res = self._call_function(self.item_config["pre_action"], context)
            if res == ItemResult.FAILURE or res is False:
                return ItemResult.FAILURE
        return self.execute_response

    def _post_hook(self, outcome: ItemResult, context: dict) -> ItemResult:
        res = outcome
        if "post_action" in self.item_config:
            res = self._call_function(self.item_config["post_action"], context, outcome)
            if res is None or res is True:
                res = outcome
        return res


class WorkflowAsynchronousStep(WorkflowDelayedStep):

    STEP_TYPE = "async"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, execute_response=ItemResult.ASYNC_EXECUTE, **kwargs)

    async def async_execute(self, context: dict) -> ItemResult:
        try:
            res = await self._async_execute(context)
            if res is None or res is True:
                res = ItemResult.SUCCESS
            if res is False:
                res = ItemResult.FAILURE
            return self._execute_wrapper(self._post_hook, context, res)
        except Exception as ex:
            logging.getLogger("pipeman.workflow").exception(ex)
            return ItemResult.FAILURE

    async def _async_execute(self, context: dict) -> ItemResult:
        return await self._call_function(self.item_config["coro"], context)


class WorkflowBatchStep(WorkflowDelayedStep):

    STEP_TYPE = "batch"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, execute_response=ItemResult.BATCH_EXECUTE)

    def batch(self, context: dict) -> ItemResult:
        res = self._execute_wrapper(self._batch_execute, context)
        return self._execute_wrapper(self._post_hook, context, res)

    def _batch_execute(self, context: dict) -> ItemResult:
        return self._call_function(self.item_config["action"], context)


class WorkflowRemoteStep(WorkflowDelayedStep):

    STEP_TYPE = "remote"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, execute_response=ItemResult.REMOTE_EXECUTE_REQUIRED)

    def complete(self, decision: bool, context: dict) -> ItemResult:
        res = ItemResult.SUCCESS if decision else ItemResult.CANCELLED
        return self._execute_wrapper(self._post_hook, context, res)


class WorkflowHookStep(WorkflowBatchStep):

    STEP_TYPE = "hook"

    def _batch_execute(self, context: dict) -> ItemResult:
        url = self.item_config["url"]
        method = self.item_config["method"].lower() if "method" in self.item_config else "get"
        resp = requests.request(method, url)
        return ItemResult.SUCCESS if resp.ok() else ItemResult.FAILURE


class WorkflowGateStep(WorkflowDelayedStep):

    STEP_TYPE = "gate"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, execute_response=ItemResult.DECISION_REQUIRED)

    def complete(self, decision: bool, context: dict) -> ItemResult:
        res = ItemResult.SUCCESS if decision else ItemResult.CANCELLED
        return self._execute_wrapper(self._post_hook, context, res)


class GenericStepFactory:

    def __init__(self, step_cls_list: list = None):
        self._cls_map = {}
        for step_type in step_cls_list:
            self._cls_map[step_type.STEP_TYPE] = step_type

    def supports_step_type(self, step_type: str) -> bool:
        return step_type in self._cls_map

    def build_step(self, step_name: str, step_type: str, step_config: dict) -> WorkflowStep:
        return self._cls_map[step_type](step_name=step_name, item_config=step_config)


class DefaultStepFactory(GenericStepFactory):

    def __init__(self):
        super().__init__([
            WorkflowHookStep,
            WorkflowGateStep,
            WorkflowBatchStep,
            WorkflowActionStep,
            WorkflowAsynchronousStep,
        ])

