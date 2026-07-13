from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.outbox import OutboxMessage
from coeus.services.release_notification_handler import ProductReleaseNotificationHandler


class UserDirectory:
    def __init__(self, user: UserAccount | None) -> None:
        self.user = user
        self.lookups: list[UUID] = []

    def get_by_id(self, user_id: UUID) -> UserAccount | None:
        self.lookups.append(user_id)
        return self.user if self.user is not None and self.user.user_id == user_id else None


class NotificationWriter:
    def __init__(self) -> None:
        self.notifications: list[tuple[object, ...]] = []
        self.emails: list[tuple[object, ...]] = []

    def notify(
        self,
        user: UserAccount,
        kind: str,
        title: str,
        body: str,
        link_path: str | None = None,
        *,
        notification_id: UUID | None = None,
    ) -> object:
        self.notifications.append((user, kind, title, body, link_path, notification_id))
        return object()

    def record_email(
        self,
        user: UserAccount,
        subject: str,
        body: str,
        *,
        email_id: UUID | None = None,
    ) -> object:
        self.emails.append((user, subject, body, email_id))
        return object()


def _user(*, active: bool = True) -> UserAccount:
    return UserAccount(
        user_id=uuid4(),
        username="requester@example.test",
        display_name="Synthetic Requester",
        roles=frozenset({RoleName.USER}),
        permissions=frozenset(),
        password_hash="synthetic",  # noqa: S106 - inert test-domain value
        is_active=active,
        clearance_level=3,
    )


def _message(user_id: UUID, payload: dict[str, Any] | None = None) -> OutboxMessage:
    product_id = uuid4()
    return OutboxMessage(
        event_id=uuid4(),
        aggregate_id=uuid4(),
        aggregate_version=2,
        event_type="product_release_notification",
        payload=payload
        or {
            "requester_user_id": str(user_id),
            "ticket_reference": "TCK-0042",
            "product_id": str(product_id),
            "product_reference": "PROD-0042",
            "product_title": "Synthetic assessment",
        },
        created_at=datetime.now(UTC),
        attempt_count=1,
    )


def test_handler_resolves_active_requester_and_preserves_release_wording() -> None:
    user = _user()
    users = UserDirectory(user)
    notifications = NotificationWriter()
    message = _message(user.user_id)

    ProductReleaseNotificationHandler(users, notifications)(message)

    product_id = UUID(str(message.payload["product_id"]))
    link = f"/store/products/{product_id}"
    assert users.lookups == [user.user_id]
    assert notifications.notifications == [
        (
            user,
            "product_released",
            "TCK-0042 released",
            "Synthetic assessment is now available in the Intelligence Store.",
            link,
            message.event_id,
        )
    ]
    assert notifications.emails == [
        (
            user,
            "Istari release: TCK-0042",
            "Your requested product PROD-0042 (Synthetic assessment) has been released. "
            f"Open Istari and view it at {link}.",
            message.event_id,
        )
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("requester_user_id", "not-a-uuid"),
        ("ticket_reference", ""),
        ("product_id", 42),
        ("product_reference", " PROD-0042"),
        ("product_title", "x" * 181),
    ],
)
def test_handler_rejects_invalid_payload_without_side_effects(field: str, value: object) -> None:
    user = _user()
    notifications = NotificationWriter()
    message = _message(user.user_id)
    message.payload[field] = value

    with pytest.raises(ValueError, match="Invalid product release notification payload"):
        ProductReleaseNotificationHandler(UserDirectory(user), notifications)(message)

    assert notifications.notifications == []
    assert notifications.emails == []


@pytest.mark.parametrize("user", [None, _user(active=False)])
def test_handler_raises_for_missing_or_inactive_requester(user: UserAccount | None) -> None:
    requester_id = user.user_id if user is not None else uuid4()
    notifications = NotificationWriter()

    with pytest.raises(LookupError, match="missing or inactive"):
        ProductReleaseNotificationHandler(UserDirectory(user), notifications)(
            _message(requester_id)
        )

    assert notifications.notifications == []
    assert notifications.emails == []


def test_handler_rejects_wrong_event_type_before_resolving_user() -> None:
    user = _user()
    users = UserDirectory(user)
    notifications = NotificationWriter()
    message = _message(user.user_id)
    object.__setattr__(message, "event_type", "ticket_shadow_changed")

    with pytest.raises(ValueError, match="Unexpected outbox event type"):
        ProductReleaseNotificationHandler(users, notifications)(message)

    assert users.lookups == []
    assert notifications.notifications == []
