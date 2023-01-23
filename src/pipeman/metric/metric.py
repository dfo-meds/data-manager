from pipeman.db import Database
from autoinject import injector
import datetime
import pipeman.db.orm as orm
import flask_login


@injector.injectable
class MetricController:

    db: Database = None

    def can_add_metric(self, metric_name):
        if not flask_login.current_user.has_permission("metrics.add"):
            return False
        if flask_login.current_user.has_permission("metrics.add_any"):
            return True
        return flask_login.current_user.has_permission(f"metrics.add.{metric_name}")

    def add_metric(self, metric_name, value, source_info=""):
        with self.db as session:
            metric = orm.Metric(
                metric_name=metric_name,
                value=str(value),
                timestamp=datetime.datetime.now(),
                source_info=source_info if source_info else None,
                username=flask_login.current_user.get_id()
            )
            session.add(metric)
            session.commit()
