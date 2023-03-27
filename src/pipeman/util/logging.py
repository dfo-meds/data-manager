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
from zrlog.logger import ImprovedLogger
from contextvars import ContextVar

_cv_logging_info = ContextVar("pipeman_logger_vars", default=None)


def set_request_info(request_vars: dict):
    val = _cv_logging_info.get({})
    val.update(request_vars)
    _cv_logging_info.set(val)


class PipemanLogger(ImprovedLogger):
    """Logger that adds a few additional parameters for logging."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._no_extras = True

    def omit_extras(self):
        self._no_extras = True

    def _log(self, *args, **kwargs):
        """Override _log()."""
        if len(args) >= 5:
            self._add_logging_extras(args[4])
        else:
            if "extra" not in kwargs:
                kwargs["extra"] = {}
            self._add_logging_extras(kwargs["extra"])
        super()._log(*args, **kwargs)

    def _add_logging_extras(self, extras):
        extras["remote_ip"] = ""
        extras["proxy_ip"] = ""
        extras["correlation_id"] = ""
        extras["client_id"] = ""
        extras["request_url"] = ""
        extras["request_method"] = ""
        extras["user_agent"] = ""
        extras["username"] = ""
        extras["referrer"] = ""
        extras["sys_username"] = ""
        extras["sys_emulated"] = ""
        extras["sys_logon"] = ""
        extras["sys_remote"] = ""
        info = _cv_logging_info.get({})
        for key in info:
            if info[key]:
                extras[key] = info[key]
