from autoinject import injector
from pipeman.db import Database
from pipeman.util import deep_update
from pipeman.workflow import WorkflowController, ItemResult
from pipeman.util.errors import DataStoreNotFoundError, PipemanConfigurationError
import zirconium as zr
import uuid
import flask


@injector.injectable_global
class DataStoreRegistry:

    def __init__(self):
        self._data_stores = {}

    def register_data_store(self, data_store_name, labels, path, enabled, push_workflow, overwrite_workflow, allow_overwrite):
        record = {
            data_store_name: {
                "label": labels or {},
                "path": path,
                "enabled": enabled,
                "push_workflow": push_workflow,
                "overwrite_workflow": overwrite_workflow,
                "allow_overwrite": allow_overwrite
            }
        }
        deep_update(self._data_stores, record)

    def allow_overwrite(self, data_store_name):
        return self._data_stores[data_store_name]["allow_overwrite"]

    def get_workflow_name(self, data_store_name, file_exists):
        if not self.data_store_exists(data_store_name):
            raise DataStoreNotFoundError(data_store_name)
        return self._data_stores[data_store_name]["overwrite_workflow" if file_exists else "push_workflow"]

    def register_data_store_from_dict(self, d: dict):
        if d:
            self._data_stores.update(d)

    def data_store_path(self, data_store_name):
        if not self.data_store_exists(data_store_name):
            raise DataStoreNotFoundError(data_store_name)
        return self._data_stores[data_store_name]["path"]

    def get_data_store_info(self, data_store_name):
        if not self.data_store_exists(data_store_name):
            raise DataStoreNotFoundError(data_store_name)
        return self._data_stores[data_store_name]

    def data_store_exists(self, data_store_name):
        if data_store_name not in self._data_stores:
            return False
        return "enabled" not in self._data_stores[data_store_name] or self._data_stores[data_store_name]["enabled"]


@injector.injectable
class FileController:

    reg: DataStoreRegistry = None
    db: Database = None
    wc: WorkflowController = None
    cfg: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        pass

    def data_store_exists(self, data_store_name):
        return self.reg.data_store_exists(data_store_name)

    def has_access(self, data_store_name):
        if not self.data_store_exists(data_store_name):
            return False
        return True

    def send_file_from_handle(self, data_store_name, filename, read_handle):
        holding_dir = self.cfg.as_path(("pipeman", "holding_dir"))
        if not (holding_dir.exists() and holding_dir.is_dir()):
            raise PipemanConfigurationError("pipeman.holding_dir does not exist")
        temp_name = str(uuid.uuid4())
        holding_file = holding_dir / temp_name
        with open(holding_file, "wb") as h:
            h.write(read_handle)
        return self.send_file(data_store_name, filename, holding_file)

    def send_file(self, data_store_name, filename, local_file_path, remove_on_completion=True):
        if not self.reg.data_store_exists(data_store_name):
            raise DataStoreNotFoundError(data_store_name)
        context = {
            "data_store_name": data_store_name,
            "filename": filename,
            "local_path": str(local_file_path),
            "remove_on_completion": remove_on_completion
        }
        result, item_id = self.wc.start_workflow("receive_send_item", "default", context)
        response = {
            "filename": filename,
            "data_store_name": data_store_name,
            "status": self.wc.interpret_status(result),
            "item_id": item_id,
            "status_url": flask.url_for("core.file_upload_status", item_id=item_id, _external=True)
        }
        return flask.jsonify(response)

    def upload_status(self, item_id):
        return flask.jsonify({
            "item_id": item_id,
            "status": self._get_upload_status(item_id),
            "status_url": flask.url_for("core.file_upload_status", item_id=item_id, _external=True)
        })

    def _get_upload_status(self, item_id):
        status = self.wc.workflow_item_status_by_id(item_id)
        if status == "complete":
            child_statuses = self.wc.workflow_item_statuses_by_object_id("send_file", item_id)
            if child_statuses:
                return child_statuses[0]
            return "unknown"
        return status
