from pipeman.db import Database
import pipeman.db.orm as orm
from autoinject import injector
import json

from pipeman.dbconfig import ValueController
from pipeman.util import deep_update
from threading import RLock
import yaml
import datetime
import decimal
import time
import zrlog


REFRESH_FREQUENCY = 15


@injector.injectable_global
class GlobalObjectRegistry:

    def __init__(self):
        self._log = zrlog.get_logger("pipeman.registries")
        self._registry = []
        self._last_setup_run = None
        self._last_setup_check = None

    def register(self, obj):
        self._registry.append(obj)

    def unregister(self, obj):
        if obj in self._registry:
            self._registry.remove(obj)

    @injector.inject
    def check_all(self, vc: ValueController = None):
        # Don't check everytime to prevent a lot of overhead (every 15 seconds)
        if self._last_setup_check and (time.monotonic() - self._last_setup_check) < REFRESH_FREQUENCY:
            return
        self._log.debug("Checking for registry updates")
        self._last_setup_check = time.monotonic()

        # Check if setup has actually run recently
        setup_last_run = vc.get_value("setup_last_run")
        if self._last_setup_run == setup_last_run:
            return

        self._log.info(f"Updating [{len(self._registry)}] registry files")
        # Do the reload
        for obj in self._registry:
            obj.reload_types()
        self._last_setup_run = setup_last_run


@injector.injectable
class ObjectController:

    db: Database = None

    @injector.construct
    def __init__(self):
        pass

    def get_object_defs(self, obj_type):
        with self.db as session:
            for obj_def in session.query(orm.ConfigRegistry).filter_by(obj_type=obj_type):
                yield obj_def.obj_name, ObjectController._from_json(obj_def.config) or {}

    def clear_object_defs(self, obj_type):
        with self.db as session:
            session.query(orm.ConfigRegistry).filter_by(obj_type=obj_type).delete()
            session.commit()

    def upsert_object_def(self, obj_type, obj_name, config):
        with self.db as session:
            obj_def = session.query(orm.ConfigRegistry).filter_by(obj_type=obj_type, obj_name=obj_name).first()
            if obj_def:
                cfg = ObjectController._from_json(obj_def.config) or {}
                deep_update(cfg, config or {})
                obj_def.config = ObjectController._to_json(cfg)
                session.commit()
            else:
                obj_def = orm.ConfigRegistry(
                    obj_type=obj_type,
                    obj_name=obj_name,
                    config=ObjectController._to_json(config)
                )
                session.add(obj_def)
                session.commit()

    @staticmethod
    def _to_json(config):
        return json.dumps(ObjectController._sanitize(config))

    @staticmethod
    def _sanitize(config):
        if isinstance(config, dict):
            for key in config:
                config[key] = ObjectController._sanitize(config[key])
            return config
        elif isinstance(config, list) or isinstance(config, tuple) or isinstance(config, set):
            return [ObjectController._sanitize(x) for x in config]
        elif isinstance(config, datetime.datetime):
            return {"_obj_type": "datetime.datetime", "_contents": config.isoformat()}
        elif isinstance(config, datetime.time):
            return {"_obj_type": "datetime.time", "_contents": config.isoformat()}
        elif isinstance(config, datetime.date):
            return {"_obj_type": "datetime.date", "_contents": config.isoformat()}
        elif isinstance(config, decimal.Decimal):
            return {"_obj_type": "decimal.Decimal", "_contents": str(config)}
        else:
            return config

    @staticmethod
    def _from_json(config_str):
        return ObjectController._unsanitize(json.loads(config_str))

    @staticmethod
    def _unsanitize(config):
        if isinstance(config, dict):
            if "_obj_type" in config and "_contents" in config:
                if config["_obj_type"] == "datetime.datetime":
                    return datetime.datetime.fromisoformat(config["_contents"])
                elif config["_obj_type"] == "datetime.time":
                    return datetime.time.fromisoformat(config["_contents"])
                elif config["_obj_type"] == "datetime.date":
                    return datetime.date.fromisoformat(config["_contents"])
                elif config["_obj_type"] == "decimal.Decimal":
                    return decimal.Decimal(config["_contents"])
            for key in config:
                config[key] = ObjectController._unsanitize(config[key])
            return config
        elif isinstance(config, list) or isinstance(config, tuple) or isinstance(config, set):
            return [ObjectController._unsanitize(x) for x in config]
        elif isinstance(config, datetime.datetime) or isinstance(config, datetime.time):
            return config.isoformat(timespec="seconds")
        elif isinstance(config, datetime.date):
            return config.isoformat()

        else:
            return config


class BaseObjectRegistry:

    gor: GlobalObjectRegistry = None

    @injector.construct
    def __init__(self, obj_type, ensure_fields=None):
        self._type_map = {}
        self._lock = RLock()
        self._obj_type = obj_type
        self._ensure_fields = ensure_fields
        self.gor.register(self)
        self._log = zrlog.get_logger("pipeman.registries")

    def __cleanup__(self):
        self.gor.unregister(self)

    def __del__(self):
        self.gor.unregister(self)

    def __iter__(self):
        return iter(self._type_map)

    def __contains__(self, key):
        return key in self._type_map

    def __getitem__(self, key):
        return self._type_map[key]

    def keys(self):
        return self._type_map.keys()

    def sorted_keys(self):
        keys = list(self._type_map.keys())
        keys.sort()
        return keys

    @injector.inject
    def reload_types(self, oc: ObjectController = None):
        with self._lock:
            found = []
            for obj_name, config in oc.get_object_defs(self._obj_type):
                found.append(obj_name)
                self._type_map[obj_name] = config
            for obj_name in list(self._type_map.keys()):
                if obj_name not in found:
                    del self._type_map[obj_name]

    @injector.inject
    def register(self, obj_name, oc: ObjectController = None, **config):
        oc.upsert_object_def(self._obj_type, obj_name, config)
        if self._ensure_fields:
            for f in self._ensure_fields:
                if f not in config:
                    config[f] = None
        if obj_name in self._type_map:
            deep_update(self._type_map[obj_name], config or {})
        else:
            self._type_map[obj_name] = config or {}

    def register_from_dict(self, cfg_dict):
        cfg_dict = cfg_dict or {}
        self._log.debug(f"Importing {len(cfg_dict)} object definitions of type [{self._obj_type}]")
        for key in cfg_dict:
            self.register(key, **cfg_dict[key])

    def register_from_yaml(self, file_path):
        self._log.notice(f"Importing object definitions of type [{self._obj_type}] from [{file_path}]")
        with open(file_path, "r", encoding="utf-8") as h:
            self.register_from_dict(yaml.safe_load(h))

    @injector.inject
    def remove_all(self, oc: ObjectController = None):
        self._log.notice(f"Removing all object definitions of type [{self._obj_type}]")
        oc.clear_object_defs(self._obj_type)
