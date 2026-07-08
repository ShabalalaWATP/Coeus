from email.message import EmailMessage
from smtplib import SMTP, SMTPException
from ssl import create_default_context
from typing import Protocol

from coeus.core.config import Settings
from coeus.domain.notifications import EmailRecord


class EmailProvider(Protocol):
    def send(self, email: EmailRecord) -> None:
        """Deliver or intentionally retain an email record."""


class OutboxEmailProvider:
    def send(self, _email: EmailRecord) -> None:
        return


class EmailDeliveryError(RuntimeError):
    """Raised when an email provider cannot deliver a message."""


class SmtpEmailProvider:
    def __init__(
        self,
        host: str,
        port: int,
        sender: str,
        username: str | None,
        password: str | None,
        starttls: bool,
        timeout_seconds: int,
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._username = username
        self._password = password
        self._starttls = starttls
        self._timeout_seconds = timeout_seconds

    def send(self, email: EmailRecord) -> None:
        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = email.to_username
        message["Subject"] = email.subject
        message.set_content(email.body)
        try:
            with SMTP(self._host, self._port, timeout=self._timeout_seconds) as smtp:
                if self._starttls:
                    smtp.starttls(context=create_default_context())
                if self._username:
                    smtp.login(self._username, self._password or "")
                smtp.send_message(message)
        except (OSError, SMTPException) as exc:
            raise EmailDeliveryError("SMTP delivery failed.") from exc


def build_email_provider(settings: Settings) -> EmailProvider:
    if settings.email_provider == "smtp":
        return SmtpEmailProvider(
            host=str(settings.smtp_host),
            port=settings.smtp_port,
            sender=str(settings.smtp_from),
            username=settings.smtp_username,
            password=settings.smtp_password,
            starttls=settings.smtp_starttls,
            timeout_seconds=settings.smtp_timeout_seconds,
        )
    return OutboxEmailProvider()
