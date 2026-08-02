from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from threading import RLock
from typing import Any, Literal
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.persistence.state_store import MemoryStateStore, StateStore
from coeus.services.audit import AuditLog

SUBSCRIPTION_NAMESPACE = "store_search_subscriptions"
MAX_SUBSCRIPTIONS_PER_USER = 50
SubscriptionCadence = Literal["manual", "daily", "weekly"]


@dataclass(frozen=True)
class SubscriptionCriteria:
    query: str | None = None
    product_type: str | None = None
    region: str | None = None
    tag: str | None = None
    source_type: str | None = None
    date_from: str | None = None
    date_to: str | None = None


@dataclass(frozen=True)
class StoreSubscription:
    subscription_id: UUID
    user_id: UUID
    name: str
    cadence: SubscriptionCadence
    enabled: bool
    criteria: SubscriptionCriteria
    created_at: datetime
    updated_at: datetime


class StoreSubscriptionService:
    """Persist private saved search criteria, never result sets or counts."""

    def __init__(self, state_store: StateStore | None, audit_log: AuditLog) -> None:
        self._state_store = state_store or MemoryStateStore()
        self._audit_log = audit_log
        self._lock: RLock = self._state_store.authority_guard()

    def list_for_user(self, user_id: UUID) -> tuple[StoreSubscription, ...]:
        with self._lock:
            return tuple(
                sorted(
                    (item for item in self._load() if item.user_id == user_id),
                    key=lambda item: (not item.enabled, item.name.casefold()),
                )
            )

    def create(
        self,
        user_id: UUID,
        *,
        name: str,
        cadence: SubscriptionCadence,
        criteria: SubscriptionCriteria,
    ) -> StoreSubscription:
        clean_name = self._clean_name(name)
        clean_criteria = self._clean_criteria(criteria)
        with self._lock:
            subscriptions = self._load()
            owned = tuple(item for item in subscriptions if item.user_id == user_id)
            if len(owned) >= MAX_SUBSCRIPTIONS_PER_USER:
                raise AppError(
                    409,
                    "subscription_limit_reached",
                    "The Intelligence Store subscription limit is reached.",
                )
            if any(item.name.casefold() == clean_name.casefold() for item in owned):
                raise AppError(
                    409,
                    "subscription_name_exists",
                    "A subscription with that name already exists.",
                )
            now = datetime.now(UTC)
            subscription = StoreSubscription(
                uuid4(), user_id, clean_name, cadence, True, clean_criteria, now, now
            )
            self._commit(
                subscriptions,
                (*subscriptions, subscription),
                "store_subscription_created",
                user_id,
                subscription.subscription_id,
            )
            return subscription

    def update(
        self,
        user_id: UUID,
        subscription_id: UUID,
        *,
        name: str,
        cadence: SubscriptionCadence,
        enabled: bool,
        criteria: SubscriptionCriteria,
    ) -> StoreSubscription:
        clean_name = self._clean_name(name)
        clean_criteria = self._clean_criteria(criteria)
        with self._lock:
            subscriptions = self._load()
            current = self._owned_subscription(subscriptions, user_id, subscription_id)
            if any(
                item.user_id == user_id
                and item.subscription_id != subscription_id
                and item.name.casefold() == clean_name.casefold()
                for item in subscriptions
            ):
                raise AppError(
                    409,
                    "subscription_name_exists",
                    "A subscription with that name already exists.",
                )
            updated = replace(
                current,
                name=clean_name,
                cadence=cadence,
                enabled=enabled,
                criteria=clean_criteria,
                updated_at=datetime.now(UTC),
            )
            next_items = tuple(
                updated if item.subscription_id == subscription_id else item
                for item in subscriptions
            )
            self._commit(
                subscriptions,
                next_items,
                "store_subscription_updated",
                user_id,
                subscription_id,
            )
            return updated

    def delete(self, user_id: UUID, subscription_id: UUID) -> None:
        with self._lock:
            subscriptions = self._load()
            self._owned_subscription(subscriptions, user_id, subscription_id)
            remaining = tuple(
                item for item in subscriptions if item.subscription_id != subscription_id
            )
            self._commit(
                subscriptions,
                remaining,
                "store_subscription_deleted",
                user_id,
                subscription_id,
            )

    @staticmethod
    def _clean_name(name: str) -> str:
        clean = name.strip()
        if not clean:
            raise AppError(422, "subscription_name_required", "Enter a subscription name.")
        return clean

    @staticmethod
    def _clean_criteria(criteria: SubscriptionCriteria) -> SubscriptionCriteria:
        values = {
            key: (value.strip() or None) if isinstance(value, str) else value
            for key, value in asdict(criteria).items()
        }
        if not any(values.values()):
            raise AppError(
                422,
                "subscription_criteria_required",
                "Choose at least one Intelligence Store search criterion.",
            )
        return SubscriptionCriteria(**values)

    @staticmethod
    def _owned_subscription(
        subscriptions: tuple[StoreSubscription, ...],
        user_id: UUID,
        subscription_id: UUID,
    ) -> StoreSubscription:
        subscription = next(
            (
                item
                for item in subscriptions
                if item.subscription_id == subscription_id and item.user_id == user_id
            ),
            None,
        )
        if subscription is None:
            raise AppError(404, "subscription_not_found", "Subscription not found.")
        return subscription

    def _load(self) -> tuple[StoreSubscription, ...]:
        payload = self._state_store.load(SUBSCRIPTION_NAMESPACE) or {}
        return tuple(_subscription_from_payload(item) for item in payload.get("subscriptions", []))

    def _save(self, subscriptions: tuple[StoreSubscription, ...]) -> None:
        self._state_store.save(
            SUBSCRIPTION_NAMESPACE,
            {"subscriptions": [_subscription_payload(item) for item in subscriptions]},
        )

    def _commit(
        self,
        previous: tuple[StoreSubscription, ...],
        updated: tuple[StoreSubscription, ...],
        event_type: str,
        actor_user_id: UUID,
        subscription_id: UUID,
    ) -> None:
        self._save(updated)
        try:
            self._audit_log.record(
                event_type,
                str(actor_user_id),
                {"subscription_id": str(subscription_id)},
            )
        except Exception:
            self._save(previous)
            raise


def _subscription_payload(subscription: StoreSubscription) -> dict[str, Any]:
    return {
        "id": str(subscription.subscription_id),
        "userId": str(subscription.user_id),
        "name": subscription.name,
        "cadence": subscription.cadence,
        "enabled": subscription.enabled,
        "criteria": asdict(subscription.criteria),
        "createdAt": subscription.created_at.isoformat(),
        "updatedAt": subscription.updated_at.isoformat(),
    }


def _subscription_from_payload(payload: dict[str, Any]) -> StoreSubscription:
    return StoreSubscription(
        subscription_id=UUID(str(payload["id"])),
        user_id=UUID(str(payload["userId"])),
        name=str(payload["name"]),
        cadence=payload["cadence"],
        enabled=bool(payload.get("enabled", True)),
        criteria=SubscriptionCriteria(**payload.get("criteria", {})),
        created_at=datetime.fromisoformat(str(payload["createdAt"])),
        updated_at=datetime.fromisoformat(str(payload["updatedAt"])),
    )
