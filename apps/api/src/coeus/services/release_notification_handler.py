"""Delivery handler for durable product-release notification intents."""

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from coeus.domain.auth import UserAccount
from coeus.domain.outbox import OutboxMessage

EVENT_TYPE = "product_release_notification"
MAX_REFERENCE_LENGTH = 120
MAX_TITLE_LENGTH = 180


class UserDirectory(Protocol):
    def get_by_id(self, user_id: UUID) -> UserAccount | None: ...


class NotificationWriter(Protocol):
    def notify(
        self,
        user: UserAccount,
        kind: str,
        title: str,
        body: str,
        link_path: str | None = None,
        *,
        notification_id: UUID | None = None,
    ) -> object: ...

    def record_email(
        self,
        user: UserAccount,
        subject: str,
        body: str,
        *,
        email_id: UUID | None = None,
    ) -> object: ...


class ProductReleaseNotificationHandler:
    """Resolve and notify the active requester named by a durable intent.

    Invalid messages raise rather than being acknowledged, allowing the outbox
    dispatcher to retain and retry or dead-letter them.
    """

    def __init__(self, users: UserDirectory, notifications: NotificationWriter) -> None:
        self._users = users
        self._notifications = notifications

    def __call__(self, message: OutboxMessage) -> None:
        if message.event_type != EVENT_TYPE:
            raise ValueError("Unexpected outbox event type for product release notification.")
        payload = _payload(message.payload)
        requester = self._users.get_by_id(payload.requester_user_id)
        if requester is None or not requester.is_active:
            raise LookupError("Product release requester is missing or inactive.")

        link_path = f"/store/products/{payload.product_id}"
        self._notifications.notify(
            requester,
            "product_released",
            f"{payload.ticket_reference} released",
            f"{payload.product_title} is now available in the Intelligence Store.",
            link_path,
            notification_id=message.event_id,
        )
        self._notifications.record_email(
            requester,
            f"Istari release: {payload.ticket_reference}",
            f"Your requested product {payload.product_reference} ({payload.product_title}) has "
            f"been released. Open Istari and view it at {link_path}.",
            email_id=message.event_id,
        )


@dataclass(frozen=True)
class _ReleasePayload:
    requester_user_id: UUID
    ticket_reference: str
    product_id: UUID
    product_reference: str
    product_title: str


def _payload(value: dict[str, Any]) -> _ReleasePayload:
    try:
        requester_user_id = _uuid(value, "requester_user_id")
        ticket_reference = _text(value, "ticket_reference", MAX_REFERENCE_LENGTH)
        product_id = _uuid(value, "product_id")
        product_reference = _text(value, "product_reference", MAX_REFERENCE_LENGTH)
        product_title = _text(value, "product_title", MAX_TITLE_LENGTH)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid product release notification payload.") from exc
    return _ReleasePayload(
        requester_user_id,
        ticket_reference,
        product_id,
        product_reference,
        product_title,
    )


def _uuid(value: dict[str, Any], field: str) -> UUID:
    raw = value[field]
    if not isinstance(raw, str):
        raise TypeError(f"{field} must be a string")
    return UUID(raw)


def _text(value: dict[str, Any], field: str, maximum: int) -> str:
    raw = value[field]
    if not isinstance(raw, str):
        raise TypeError(f"{field} must be a string")
    normalised = raw.strip()
    if not normalised or len(normalised) > maximum or normalised != raw:
        raise ValueError(f"{field} is invalid")
    return normalised
