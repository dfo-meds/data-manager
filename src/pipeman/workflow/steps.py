import importlib
import flask_login
import requests
import zrlog
from enum import Enum
import pipeman.db.orm as orm
import typing as t


# gettext('pipeman.label.witem.step.in-progress')
# gettext('pipeman.label.witem.step.failure')
# gettext('pipeman.label.witem.step.cancelled')
# gettext('pipeman.label.witem.step.pending')
# gettext('pipeman.label.witem.step.complete')
# gettext('pipeman.label.witem.step.skipped')
# gettext('pipeman.label.witem.status.complete')
# gettext('pipeman.label.witem.status.failure')
# gettext('pipeman.label.witem.status.cancelled')
# gettext('pipeman.label.witem.status.in-progress')
# gettext('pipeman.label.witem.status.unknown')
# "gettext('pipeman.label.witem.status.failure')"
# "gettext('pipeman.label.witem.status.decision_required')"
# "gettext('pipeman.label.witem.status.batch_execute')"
# gettext('pipeman.label.witem.status.async_delay')
# gettext('pipeman.label.witem.status.batch_delay')
# "gettext('pipeman.label.witem.status.async_execute')"
# "gettext('pipeman.label.witem.status.cancelled')"
# "gettext('pipeman.label.witem.status.remote_exec_queued')"
# "gettext('pipeman.label.witem.status.in_progress')"
# "gettext('pipeman.label.witem.status.complete')"

class StepStatus(Enum):

    FAILURE = "FAILURE"
    DECISION_REQUIRED = "DECISION_REQUIRED"
    BATCH_EXECUTE = "BATCH_EXECUTE"
    ASYNC_DELAY = "ASYNC_DELAY"
    BATCH_DELAY = "BATCH_DELAY"
    ASYNC_EXECUTE = "ASYNC_EXECUTE"
    CANCELLED = "CANCELLED"
    REMOTE_EXECUTE_REQUIRED = "REMOTE_EXEC_QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    COMPLETED = "COMPLETED"

    @staticmethod
    def interpret_status(res):
        if res == StepStatus.SUCCESS:
            return "complete"
        elif res == StepStatus.FAILURE:
            return "failure"
        elif res == StepStatus.COMPLETED:
            return 'complete'
        elif res == StepStatus.CANCELLED:
            return "cancelled"
        else:
            return "in-progress"


class ItemResult(Enum):

    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    BATCH_EXECUTE = "batch_execute"
    ASYNC_EXECUTE = "async_execute"
    DECISION_REQUIRED = "decision_required"
    REMOTE_EXECUTE_REQUIRED = "remote_required"
    BATCH_DELAY = "batch_delay"
    ASYNC_DELAY = "async_delay"

    @staticmethod
    def interpret_result(res):
        if res == ItemResult.SUCCESS:
            return 'complete'
        elif res == ItemResult.FAILURE:
            return 'failure'
        elif res == ItemResult.CANCELLED:
            return 'cancelled'
        else:
            return 'in-progress'

    @staticmethod
    def get_item_status_after_step(res):
        if res == ItemResult.FAILURE:
            return StepStatus.FAILURE, ItemNextAction.FAILURE
        elif res == ItemResult.CANCELLED:
            return StepStatus.CANCELLED, ItemNextAction.FAILURE
        elif res == ItemResult.DECISION_REQUIRED:
            return StepStatus.DECISION_REQUIRED, ItemNextAction.NO_ACTION
        elif res == ItemResult.BATCH_DELAY:
            return StepStatus.BATCH_DELAY, ItemNextAction.NO_ACTION
        elif res == ItemResult.BATCH_EXECUTE:
            return StepStatus.BATCH_EXECUTE, ItemNextAction.NO_ACTION
        elif res == ItemResult.SUCCESS:
            return StepStatus.IN_PROGRESS, ItemNextAction.CONTINUE
        elif res == ItemResult.ASYNC_DELAY:
            return StepStatus.ASYNC_DELAY, ItemNextAction.NO_ACTION
        elif res == ItemResult.ASYNC_EXECUTE:
            return StepStatus.ASYNC_EXECUTE, ItemNextAction.NO_ACTION


class ItemNextAction:

    CONTINUE = 0
    NO_ACTION = 1
    FAILURE = 2


class WorkflowStep:

    def __init__(self, step_name: str, item_config: dict):
        self.item: t.Optional[orm.WorkflowItem] = None
        self.item_config = item_config
        self.step_name = step_name
        self.output = []
        self._log = zrlog.get_logger("pipeman.workflow")

    def set_item(self, item):
        self.item = item

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
            self._log.exception(f"Error while executing step function {str(call_me)}")
            self.output.append(f"Error calling {str(call_me)}: {str(ex)}")
            return ItemResult.FAILURE

    def _execute(self, context: dict) -> ItemResult:
        return ItemResult.SUCCESS

    def _call_function(self, func_path, *args, **kwargs):
        mod_pos = func_path.rfind(".")
        module_name = func_path[0:mod_pos]
        func_name = func_path[mod_pos+1:]
        module = importlib.import_module(module_name)
        func = getattr(module, func_name)
        return func(self, *args, **kwargs)


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
            res = self._call_function(self.item_config["pre_action"],  context)
            if res == ItemResult.FAILURE or res is False:
                return ItemResult.FAILURE
        return self.execute_response

    def _post_hook(self, context: dict, outcome: ItemResult) -> ItemResult:
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
            self._log.exception("Error executing async step")
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
