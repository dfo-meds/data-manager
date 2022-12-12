from enum import Enum
import importlib
import flask_login
import flask
from pipeman.util.flask import ConfirmationForm
from pipeman.util import deep_update
from pipeman.util.errors import StepNotFoundError, StepConfigurationError, WorkflowNotFoundError, WorkflowItemNotFoundError
from autoinject import injector
from pipeman.db import Database
from pipeman.i18n import MultiLanguageString
import json
import pipeman.db.orm as orm
import datetime
import requests
import time
import zirconium as zr
from pipeman.i18n import gettext, format_datetime
import logging
import markupsafe


class ItemResult(Enum):

    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    BATCH_EXECUTE = "batch_execute"
    DECISION_REQUIRED = "decision_required"


@injector.injectable_global
class WorkflowRegistry:

    def __init__(self):
        self._steps = {}
        self._workflows = {}
        self._factories = []
        self._factories.append(DefaultStepFactory())

    def register_step_factory(self, factory):
        self._factories.append(factory)

    def step_display(self, step_name):
        return MultiLanguageString(self._steps[step_name]['label'])

    def register_workflow(self, workflow_name, category, label, steps, enabled=True):
        record = {
            category: {
                workflow_name: {
                    "label": label,
                    "steps": steps,
                    "enabled": enabled
                }
            }
        }
        deep_update(self._workflows, record)

    def workflow_display(self, category_name, workflow_name):
        return MultiLanguageString(self._workflows[category_name][workflow_name]['label']) if category_name in self._workflows and workflow_name in self._workflows[category_name] else "?"

    def list_workflows(self, category_name):
        return [
            (wn, MultiLanguageString(self._workflows[category_name][wn]["label"]))
            for wn in self._workflows[category_name]
        ] if category_name in self._workflows else []

    def register_step(self, step_name, label, step_type, item_config):
        record = {
            step_name: {
                "label": label,
                "step_type": step_type,
                **item_config
            }
        }
        deep_update(self._steps, record)

    def register_steps_from_dict(self, d: dict):
        if d:
            deep_update(self._steps, d)

    def register_workflows_from_dict(self, d: dict):
        if d:
            deep_update(self._workflows, d)

    def construct_step(self, step_name):
        if step_name not in self._steps:
            raise StepNotFoundError(step_name)
        step_config = self._steps[step_name]
        for factory in self._factories:
            if factory.supports_step_type(step_config["step_type"]):
                return factory.build_step(step_name, step_config["step_type"], step_config)
        raise StepConfigurationError(f"Invalid step type for {step_name}: {step_config['step_type']}")

    def step_list(self, workflow_type, workflow_name):
        if workflow_type not in self._workflows:
            raise WorkflowNotFoundError(f"{workflow_type}-{workflow_name}")
        if workflow_name not in self._workflows[workflow_type]:
            raise WorkflowNotFoundError(f"{workflow_type}-{workflow_name}")
        return self._workflows[workflow_type][workflow_name]["steps"]

    def list_workflows(self, workflow_type):
        return [
            (x, MultiLanguageString(self._workflows[workflow_type][x]["label"]))
            for x in self._workflows[workflow_type]
            if "enabled" not in self._workflows[workflow_type][x] or self._workflows[workflow_type][x]["enabled"]
        ]


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
            ('pipeman.workflow_item.object_link', markupsafe.Markup(f"<a href='{self.object_link()}'>{self.object_link_text()}</a>")),
            ('pipeman.workflow_item.type', gettext(f'pipeman.workflow_types.{self.item.workflow_type}')),
            ('pipeman.workflow_item.name', self.reg.workflow_display(self.item.workflow_type, self.item.workflow_name)),
            ('pipeman.workflow_item.created', format_datetime(self.item.created_date)),
            ('pipeman.workflow_item.status', gettext(f'pipeman.workflow_statuses.{self.item.status.lower()}')),
        ]

    def steps(self):
        decision_list = {}
        for decision in self.item.decisions:
            decision_list[decision.step_name] = decision
        step_list = json.loads(self.item.step_list)
        for idx, step in enumerate(step_list):
            data = [self.reg.step_display(step)]
            if step in decision_list:
                template = gettext("pipeman.workflow_item.gate_completed" if decision_list[step].decision else "pipeman.workflow_item.gate_cancelled")
                occurances = template.count("{")
                if occurances > 1:
                    template = template.format(decision_list[step].decider_id, format_datetime(decision_list[step].decision_date))
                elif occurances == 1:
                    template = template.format(decision_list[step].decider_id)
                data.append(template)
            else:
                data.append("")
            if self.item.completed_index is None and idx == 0:
                data.append("in-progress")
            elif self.item.completed_index >= idx:
                data.append("complete")
            elif self.item.completed_index == (idx - 1):
                data.append("in-progress")
            else:
                data.append("pending")
            yield data


@injector.injectable
class WorkflowController:

    db: Database = None
    reg: WorkflowRegistry = None
    cfg: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        pass

    def start_workflow(self, workflow_type, workflow_name, workflow_context, object_id):
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
            return item.status

    def workflow_form(self, item_id, decision: bool = True):
        with self.db as session:
            item = session.query(orm.WorkflowItem).filter_by(id=item_id).first()
            if not item:
                return flask.abort(404)
            if not self._has_access(item, "decide"):
                return flask.abort(403)
            item_url = flask.url_for("core.view_item", item_id=item_id)
            base_key = "pipeman.workflow.continue" if decision else 'pipeman.workflow.cancel'
            form = ConfirmationForm()
            if form.validate_on_submit():
                self._make_decision(item, session, decision)
                return flask.redirect(item_url)
            return flask.render_template(
                "form.html",
                form=form,
                instructions=gettext(f"{base_key}.instructions"),
                title=gettext(f"{base_key}.title"),
                back=item_url
            )

    def view_item_page(self, item_id):
        with self.db as session:
            item = session.query(orm.WorkflowItem).filter_by(id=item_id).first()
            if not item:
                return flask.abort(404)
            if not self._has_access(item, "view"):
                return flask.abort(403)
            return flask.render_template(
                "view_workflow_item.html",
                item=ItemDisplayWrapper(item),
                title=gettext("pipeman.workflow_view.title")
            )

    def list_workflow_items_page(self):
        return flask.render_template(
            "list_workflow_items.html",
            items=self._iterate_workflow_items(),
            title=gettext("pipeman.workflow_list.title")
        )

    def _iterate_workflow_items(self):
        with self.db as session:
            items = session.query(orm.WorkflowItem).filter_by(status='DECISION_REQUIRED')
            for item in items:
                if not self._has_access(item, 'view'):
                    continue
                actions = [
                    (flask.url_for('core.view_item', item_id=item.id),'pipeman.general.view')
                ]
                if self._has_access(item, 'decide'):
                    actions.extend([
                        (flask.url_for('core.approve_item', item_id=item.id), 'pipeman.workflow_item.approve'),
                        (flask.url_for('core.cancel_item', item_id=item.id), 'pipeman.workflow_item.cancel'),
                    ])
                yield ItemDisplayWrapper(item), actions

    def _has_access(self, item, mode):
        step, steps = self._build_next_step(item)
        ctx = json.loads(item.context)
        if step is None:
            return flask_login.current_user.has_permission("action_items.view_completed")
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

    def _handle_step_result(self, result, item, session, steps, ctx):
        if result == ItemResult.FAILURE:
            item.status = "FAILURE"
        elif result == ItemResult.DECISION_REQUIRED:
            item.status = "DECISION_REQUIRED"
        elif result == ItemResult.BATCH_EXECUTE:
            item.status = "BATCH_EXECUTE"
        elif result == ItemResult.CANCELLED:
            item.status = "CANCELLED"
        else:
            item.completed_index += 1
            item.status = "IN_PROGRESS"
        item.context = json.dumps(ctx)
        session.commit()
        if item.status == "IN_PROGRESS":
            self._start_next_step(item, session, steps, ctx)

    def _build_next_step(self, item, steps=None):
        steps = steps or json.loads(item.step_list)
        next_index = item.completed_index
        if next_index >= len(steps):
            item.status = "COMPLETE"
            return None, None
        return self.reg.construct_step(steps[next_index]), steps

    def _start_next_step(self, item, session, steps=None, ctx=None):
        step, steps = self._build_next_step(item, steps)
        if step is None:
            session.commit()
            return
        ctx = ctx or json.loads(item.context)
        result = step.execute(ctx)
        self._handle_step_result(result, item, session, steps, ctx)

    def _batch_execute(self, item, session):
        step, steps = self._build_next_step(item)
        if step is None:
            session.commit()
            return
        ctx = json.loads(item.context)
        result = step.batch(ctx)
        self._handle_step_result(result, item, session, steps, ctx)

    def _make_decision(self, item, session, decision: bool):
        step, steps = self._build_next_step(item)
        if step is None:
            session.commit()
            return
        ctx = json.loads(item.context)
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


class WorkflowStep:

    def __init__(self, step_name: str, item_config: dict):
        self.item_config = item_config
        self.step_name = step_name

    def execute(self, context: dict) -> ItemResult:
        return self._execute_wrapper(self._execute, context)

    def batch(self, context: dict) -> ItemResult:
        return ItemResult.SUCCESS

    def allow_view(self, context: dict) -> bool:
        return False

    def allow_decision(self, context: dict) -> bool:
        return False

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


class WorkflowBatchStep(WorkflowDelayedStep):

    STEP_TYPE = "batch"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, execute_response=ItemResult.BATCH_EXECUTE)

    def batch(self, context: dict) -> ItemResult:
        res = self._execute_wrapper(self._batch_execute, context)
        return self._execute_wrapper(self._post_hook, context, res)

    def _batch_execute(self, context: dict) -> ItemResult:
        return self._call_function(self.item_config["action"], context)


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

    def allow_view(self, context: dict) -> bool:
        if "access_check" in self.item_config:
            if not self._call_function(self.item_config["access_check"], context, 'view'):
                return False
        return True

    def allow_decision(self, context: dict) -> bool:
        if "require_permission" in self.item_config:
            if not flask_login.current_user.has_permission(self.item_config["require_permission"]):
                return False
        if "access_check" in self.item_config:
            if not self._call_function(self.item_config["access_check"], context, 'decide'):
                return False
        return True

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
            WorkflowActionStep
        ])
