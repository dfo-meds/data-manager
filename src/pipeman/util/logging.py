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
        extras["remote_ip"] = self.rinfo.remote_ip() or ""
        extras["proxy_ip"] = self.rinfo.proxy_ip() or ""
        extras["correlation_id"] = self.rinfo.correlation_id() or ""
        extras["client_id"] = self.rinfo.client_id() or ""
        extras["request_url"] = self.rinfo.request_url() or ""
        extras["user_agent"] = self.rinfo.user_agent() or ""
        extras["username"] = self.rinfo.username() or ""
        extras["referrer"] = self.rinfo.referrer() or ""
        extras["sys_username"] = self.rinfo.sys_username() or ""
        extras["sys_emulated"] = self.rinfo.sys_emulated_username() or ""
        extras["sys_logon"] = self.rinfo.sys_logon_time() or ""
        extras["sys_remote"] = self.rinfo.sys_remote_addr() or ""
