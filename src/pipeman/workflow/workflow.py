import yaml
from pipeman.util.errors import StepNotFoundError, StepConfigurationError, WorkflowNotFoundError
from autoinject import injector
from pipeman.i18n import MultiLanguageString
from pipeman.db import BaseObjectRegistry
from .steps import DefaultStepFactory


@injector.injectable_global
class WorkflowRegistry:

    def __init__(self):
        self._steps = BaseObjectRegistry("step")
        self._workflows = BaseObjectRegistry("workflow")
        self._factories = []
        self._factories.append(DefaultStepFactory())

    def remove_all(self):
        self._steps.remove_all()
        self._workflows.remove_all()

    def __cleanup__(self):
        self._steps.__cleanup__()
        self._workflows.__cleanup__()

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

    def list_all_steps(self):
        for s in self._steps:
            yield s, self._steps[s]

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

    def list_all_workflows(self):
        for key in self._workflows:
            yield key, self._workflows[key]

    def list_workflows(self, workflow_type: str):
        for key in self._workflows:
            if not key.startswith(f"{workflow_type}__"):
                continue
            if "enabled" in self._workflows[key] and not self._workflows[key]["enabled"]:
                continue
            yield key[len(workflow_type)+2:], MultiLanguageString(self._workflows[key]["label"] or {"und": key})

