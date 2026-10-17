"""Single-recipient SMTP sending helpers for the desktop mail sender."""

from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
import mimetypes
import re
import smtplib
import socket
import ssl
import threading
import time
from typing import Callable, Iterable

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@dataclass(frozen=True)
class SmtpSettings:
    host: str
    port: int
    security: str  # "SSL" or "STARTTLS"


COMMON_PROVIDERS: dict[str, SmtpSettings] = {
    "qq.com": SmtpSettings("smtp.qq.com", 465, "SSL"),
    "gmail.com": SmtpSettings("smtp.gmail.com", 465, "SSL"),
    "outlook.com": SmtpSettings("smtp.office365.com", 587, "STARTTLS"),
    "hotmail.com": SmtpSettings("smtp.office365.com", 587, "STARTTLS"),
    "live.com": SmtpSettings("smtp.office365.com", 587, "STARTTLS"),
    "163.com": SmtpSettings("smtp.163.com", 465, "SSL"),
    "126.com": SmtpSettings("smtp.126.com", 465, "SSL"),
}


def is_valid_email(value: str) -> bool:
    return bool(EMAIL_PATTERN.fullmatch(value.strip()))


def parse_recipients(text: str) -> tuple[list[str], list[str]]:
    """Return de-duplicated valid addresses and invalid input lines."""
    recipients: list[str] = []
    invalid: list[str] = []
    seen: set[str] = set()

    for raw_line in text.splitlines():
        address = raw_line.strip()
        if not address:
            continue
        if not is_valid_email(address):
            invalid.append(address)
            continue
        normalized = address.casefold()
        if normalized not in seen:
            recipients.append(address)
            seen.add(normalized)
    return recipients, invalid


def suggested_smtp(sender_email: str) -> SmtpSettings | None:
    domain = sender_email.strip().rsplit("@", 1)[-1].casefold()
    return COMMON_PROVIDERS.get(domain)


def build_message(
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    attachments: Iterable[Path],
) -> EmailMessage:
    """Build a new message for exactly one recipient."""
    message = EmailMessage()
    message["From"] = formataddr(("", sender))
    message["To"] = recipient  # Intentionally a single address; never use CC/BCC.
    message["Subject"] = subject
    message.set_content(body)

    for attachment in attachments:
        mime_type, encoding = mimetypes.guess_type(attachment.name)
        if mime_type is None or encoding is not None:
            maintype, subtype = "application", "octet-stream"
        else:
            maintype, subtype = mime_type.split("/", 1)
        message.add_attachment(
            attachment.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=attachment.name,
        )
    return message


def send_one(
    settings: SmtpSettings,
    sender: str,
    password: str,
    recipient: str,
    subject: str,
    body: str,
    attachments: Iterable[Path],
    timeout: float = 30,
) -> None:
    """Log in and send one separately-created email via SMTP."""
    message = build_message(sender, recipient, subject, body, attachments)
    context = ssl.create_default_context()

    if settings.security == "SSL":
        with smtplib.SMTP_SSL(settings.host, settings.port, timeout=timeout, context=context) as smtp:
            smtp.login(sender, password)
            smtp.send_message(message, from_addr=sender, to_addrs=[recipient])
    elif settings.security == "STARTTLS":
        with smtplib.SMTP(settings.host, settings.port, timeout=timeout) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            smtp.login(sender, password)
            smtp.send_message(message, from_addr=sender, to_addrs=[recipient])
    else:
        raise ValueError("安全方式必须为 SSL 或 STARTTLS。")


class MailSendWorker(threading.Thread):
    """Background sequential sender. Callbacks are invoked from this worker thread."""

    def __init__(
        self,
        settings: SmtpSettings,
        sender: str,
        password: str,
        recipients: list[str],
        subject: str,
        body: str,
        attachments: list[Path],
        interval_seconds: float,
        on_status: Callable[[str, str, str], None],
        on_finished: Callable[[int, int, bool], None],
    ) -> None:
        super().__init__(daemon=True)
        self.settings = settings
        self.sender = sender
        self.password = password
        self.recipients = recipients
        self.subject = subject
        self.body = body
        self.attachments = attachments
        self.interval_seconds = interval_seconds
        self.on_status = on_status
        self.on_finished = on_finished
        self.run_event = threading.Event()
        self.run_event.set()
        self.stop_event = threading.Event()

    def pause(self) -> None:
        self.run_event.clear()

    def resume(self) -> None:
        self.run_event.set()

    def stop(self) -> None:
        self.stop_event.set()
        self.run_event.set()

    def _wait_until_allowed(self) -> bool:
        while not self.stop_event.is_set():
            if self.run_event.wait(timeout=0.2):
                return True
        return False

    def _wait_interval(self) -> bool:
        deadline = time.monotonic() + self.interval_seconds
        while time.monotonic() < deadline:
            if self.stop_event.is_set():
                return False
            if not self.run_event.is_set():
                if not self._wait_until_allowed():
                    return False
                deadline = time.monotonic() + self.interval_seconds
            time.sleep(0.1)
        return not self.stop_event.is_set()

    def run(self) -> None:
        success_count = 0
        failure_count = 0
        was_stopped = False
        try:
            for index, recipient in enumerate(self.recipients):
                if not self._wait_until_allowed():
                    was_stopped = True
                    break
                self.on_status(recipient, "发送中", "")
                try:
                    send_one(
                        self.settings,
                        self.sender,
                        self.password,
                        recipient,
                        self.subject,
                        self.body,
                        self.attachments,
                    )
                except (OSError, smtplib.SMTPException, ValueError) as exc:
                    failure_count += 1
                    self.on_status(recipient, "失败", str(exc))
                except Exception as exc:  # Keep the batch moving while recording unexpected errors.
                    failure_count += 1
                    self.on_status(recipient, "失败", f"意外错误: {exc}")
                else:
                    success_count += 1
                    self.on_status(recipient, "成功", "")

                if index < len(self.recipients) - 1 and not self._wait_interval():
                    was_stopped = self.stop_event.is_set()
                    if was_stopped:
                        break
        finally:
            self.on_finished(success_count, failure_count, was_stopped or self.stop_event.is_set())

