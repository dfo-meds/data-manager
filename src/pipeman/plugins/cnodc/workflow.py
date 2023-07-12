import zrlog
import zirconium as zr
from autoinject import injector
import requests
import base64


@injector.inject
def notify_erddaputil_http(step, context, cfg: zr.ApplicationConfig = None):
    log = zrlog.get_logger("pipeman.cnodc")
    erddap_cluster = step.item_config["erddap_cluster"]
    notify_endpoint = cfg.as_str(("cnodc", "erddaputil", erddap_cluster, "notify_base_url"), default=None)
    username = cfg.as_str(("cnodc", "erddaputil", erddap_cluster, "username"), default=None)
    password = cfg.as_str(("cnodc", "erddaputil", erddap_cluster, "password"), default=None)
    if not notify_endpoint:
        step.output.append("skipped")
        return
    if not username:
        step.output.append("skipped")
        return
    if not password:
        step.output.append("skipped")
        return
    if not notify_endpoint.endswith("/"):
        notify_endpoint += "/"
    notify_endpoint += "datasets/compile"
    unpwd = f"{username}:{password}"
    try:
        body = {}
        resp = requests.post(
            url=notify_endpoint,
            headers={
                "Authorization": f"basic {base64.b64encode(unpwd.encode('utf-8')).decode('ascii')}"
            },
            json=body
        )
        j = resp.json()
        if j and "message" in j:
            if isinstance(j["message"], list):
                step.output.extend(j["message"])
            else:
                step.output.append(j["message"])
        resp.raise_for_status()
    except Exception as ex:
        log.notice(f"Request to POST {notify_endpoint} failed, body: [{body}]")
        raise ex
