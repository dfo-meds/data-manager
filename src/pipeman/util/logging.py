"""Utilities for extending the Flask application with extra logging parameters.
This class adds the additional parameters to Flask logging:
- proxy_ip
- remote_addr
- correl_id (X-Correlation-ID header)
- client_id (X-Client-ID header)
- url
- user_agent
- username
- referrer
"""
from autoinject import injector
from pipeman.util.flask import RequestInfo
from zrlog.logger import ImprovedLogger


class PipemanLogger(ImprovedLogger):
    """Logger that adds a few additional parameters for logging."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _log(self, *args, **kwargs):
        """Override _log()."""
        if len(args) >= 5:
            self._add_logging_extras(args[4])
        else:
            if "extra" not in kwargs:
                kwargs["extra"] = {}
            self._add_logging_extras(kwargs["extra"])
        super()._log(*args, **kwargs)

    @injector.inject
    def _add_logging_extras(self, extras, rinfo: RequestInfo = None):
        """Extend extras by adding the request info."""
        extras["remote_ip"] = rinfo.remote_ip() or ""
        extras["proxy_ip"] = rinfo.proxy_ip() or ""
        extras["correlation_id"] = rinfo.correlation_id() or ""
        extras["client_id"] = rinfo.client_id() or ""
        extras["request_url"] = rinfo.request_url() or ""
        extras["user_agent"] = rinfo.user_agent() or ""
        extras["username"] = rinfo.username() or ""
        extras["referrer"] = rinfo.referrer() or ""
        extras["sys_username"] = rinfo.sys_username() or ""
        extras["sys_emulated"] = rinfo.sys_emulated_username() or ""
        extras["sys_logon"] = rinfo.sys_logon_time() or ""
        extras["sys_remote"] = rinfo.sys_remote_addr() or ""
