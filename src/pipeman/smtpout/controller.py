import email.message
import logging
import multiprocessing
import pathlib
import smtplib
import typing as t
import queue
import logging.handlers
import atexit

import jinja2
from autoinject import injector
import zirconium as zr
import zrlog
from jinja2 import select_autoescape

from pipeman.workflow import WorkflowController, ItemResult
from pipeman.workflow.steps import WorkflowStep

EMAIL_OR_LIST = t.Union[str, t.Iterable[str], None]


@injector.injectable_global
class EmailController:

    config: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self._log = zrlog.get_logger("pipeman.email")
        self._connect_args = {
            "host": self.config.as_str(("pipeman", "email", "host"), default=""),
            "port": self.config.as_int(("pipeman", "email", "port"), default=0),
            'local_hostname': self.config.as_str(("pipeman", "email", "local_hostname"), default=None),
            "timeout": self.config.as_int(("pipeman", "email", "connect_timeout"), default=None),
        }
        self._login_args = {
            "user": self.config.as_str(("pipeman", "email", "username"), default=None),
            "password": self.config.as_str(("pipeman", "email", "password"), default=None),
        }
        self._use_ssl = self.config.as_bool(("pipeman", "email", "use_ssl"), default=False)
        self._start_tls = self.config.as_bool(("pipeman", "email", "start_tls"), default=True) and not self._use_ssl
        self._from_email = self.config.as_str(("pipeman", "email", "send_from"), default="no-reply@example.com")
        self._dummy_send = self.config.as_bool(("pipeman", "email", "no_send"), default=True)
        self.admin_emails = self.config.as_list(("pipeman", "email", "admin_emails"), default=[])
        extra_template_folders = self.config.as_list(("pipeman", "email", "template_folders"), default=None)
        if extra_template_folders:
            extra_template_folders = [
                pathlib.Path(x)
                for x in reversed(extra_template_folders)
            ]
        else:
            extra_template_folders = []
        base_path = pathlib.Path(__file__).absolute().parent / "templates"
        self._email_jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader([base_path, *extra_template_folders]),
            autoescape=select_autoescape()
        )
        self._template_cache = {}

    def send_template(self, template_name, template_lang, to_emails=None, cc_emails=None, bcc_emails=None, immediate: bool = False, **template_args):
        subject, message_txt, message_html = self._get_template_content(template_name, template_lang, template_args)
        return self.send_email(
            to_emails,
            subject,
            message_txt,
            message_html,
            cc_emails,
            bcc_emails,
            immediate
        )

    def _get_template_content(self, name, lang, kwargs) -> tuple[str, str, str]:
        message_txt = self._render_template_content(name, lang, "txt", kwargs)
        message_html = self._render_template_content(name, lang, "html", kwargs)
        subject = self._render_template_content(name + ".subject", lang, "txt", kwargs).strip("\r\n\t ")
        return subject or f"{name}", message_txt, message_html

    def _render_template_content(self, name, lang, extension, kwargs):
        file_name_options = [
            f"{name}.{lang}.{extension}",
            f"{name}.{extension}"
        ]
        try:
            template = self._email_jinja_env.select_template(file_name_options)
            return template.render(**kwargs)
        except jinja2.TemplatesNotFound:
            return None

    def send_email(self, to_emails, subject: str, message_txt: str = None, message_html: str = None, cc_emails = None, bcc_emails = None, immediate: bool = False) -> bool:
        if immediate:
            return self.direct_send_email(to_emails, subject, message_txt, message_html, cc_emails, bcc_emails)
        else:
            return self.delayed_send_email(to_emails, subject, message_txt, message_html, cc_emails, bcc_emails)

    @injector.inject
    def delayed_send_email(self, to_emails, subject: str, message_txt: str = None, message_html: str = None, cc_emails = None, bcc_emails = None, wc: WorkflowController = None) -> bool:
        status, id = wc.start_workflow(
            "send_email",
            "default",
            {
                "to_emails": to_emails,
                "subject": subject,
                "message_txt": message_txt,
                "message_html": message_html,
                "cc_emails": cc_emails,
                "bcc_emails": bcc_emails,
            },
            object_id=None,
            object_type=None
        )
        return status != "FAILURE"

    def direct_send_email(self, to_emails: EMAIL_OR_LIST, subject: str, message_txt: str = None, message_html: str = None, cc_emails: EMAIL_OR_LIST = None, bcc_emails: EMAIL_OR_LIST = None, _no_output: bool = False) -> bool:
        # Build message
        to_addrs = self._standardize_email_list(to_emails)
        if cc_emails:
            to_addrs.extend(self._standardize_email_list(cc_emails))
        if bcc_emails:
            to_addrs.extend(self._standardize_email_list(bcc_emails))
        msg = email.message.EmailMessage()
        msg['Subject'] = subject
        msg['To'] = self._standardize_email_list(to_emails)
        if cc_emails:
            msg['CC'] = self._standardize_email_list(cc_emails)
        msg['From'] = self._from_email
        msg.set_content(message_txt)
        if message_html:
            msg.add_alternative(message_html, subtype='html')
        if not self._dummy_send:
            return self._send_smtp_message(msg, to_addrs)
        elif not _no_output:
            print(msg.as_string())
            return False
        else:
            return False

    def _send_smtp_message(self, msg, to_addrs):
        # Actually send it
        if not to_addrs:
            return False
        smtp = smtplib.SMTP
        if self._use_ssl:
            smtp = smtplib.SMTP_SSL
        with smtp(**self._connect_args) as smtp:
            if self._start_tls:
                smtp.starttls()
            if self._login_args['user'] or self._login_args['password']:
                smtp.login(**self._login_args)
            smtp.send_message(msg, to_addrs=to_addrs)
            return True

    def _standardize_email_list(self, emails: EMAIL_OR_LIST) -> list:
        if emails is None:
            return []
        if isinstance(emails, str):
            return [emails]
        return list(emails)


@injector.inject
def send_email(step: WorkflowStep, context, ec: EmailController = None):
    if ec.direct_send_email(
        context['to_emails'],
        context['subject'],
        context['message_txt'],
        context['message_html'],
        context['cc_emails'],
        context['bcc_emails']
    ):
        step.output.append(f"Email sent successfully")
        return ItemResult.SUCCESS
    else:
        step.output.append(f"No email was sent")
        return ItemResult.FAILURE


class EmailLogHandler(logging.Handler):

    emails: EmailController = None

    @injector.construct
    def __init__(self, *args, subject_line=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._subject_formatter = logging.Formatter(subject_line or "Pipeman Event - %(levelname)s")

    def emit(self, record: logging.LogRecord):
        self.emails.direct_send_email(
            self.emails.admin_emails,
            subject=self._subject_formatter.format(record),
            message_txt=self.format(record)
        )


class QueuedEmailLogHandler(logging.handlers.QueueHandler):

    def __init__(self, queue, level_name=logging.ERROR, subject_line=None):
        queue = multiprocessing.Queue()
        super().__init__(queue)
        self.setLevel(level_name)
        self._email_handler = EmailLogHandler(subject_line=subject_line)
        self._listener = logging.handlers.QueueListener(queue, self._email_handler)
        self._listener.start()
        atexit.register(self._listener.stop)
