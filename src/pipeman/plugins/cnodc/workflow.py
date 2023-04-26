import base64

import zirconium as zr
from autoinject import injector
import requests
import base64


@injector.inject
def notify_erddaputil_http(step, context, cfg: zr.ApplicationConfig = None):
    erddap_cluster = step.item_config["erddap_cluster"]
    notify_endpoint = cfg.as_str(("cnodc", "erddaputil", erddap_cluster, "notify_base_url"), default=None)
    username = cfg.as_str(("cnodc", "erddaputil", erddap_cluster, "username"), default=None)
    password = cfg.as_str(("cnodc", "erddaputil", erddap_cluster, "password"), default=None)
    if notify_endpoint is None:
        step.output.append("skipped")
        return
    if username is None:
        step.output.append("skipped")
        return
    if password is None:
        step.output.append("skipped")
        return
    if not notify_endpoint.endswith("/"):
        notify_endpoint += "/"
    notify_endpoint += "datasets/compile"
    unpwd = f"{username}:{password}"
    resp = requests.post(
        url=notify_endpoint,
        headers={
            "Authorization": f"basic {base64.b64encode(unpwd.encode('utf-8')).decode('ascii')}"
        }
    )
    j = resp.json()
    if j and "message" in j:
        if isinstance(j["message"], list):
            step.output.extend(j["message"])
        else:
            step.output.append(j["message"])
    resp.raise_for_status()
