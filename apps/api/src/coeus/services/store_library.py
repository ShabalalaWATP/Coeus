from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.persistence.state_store import MemoryStateStore, StateStore
from coeus.services.audit import AuditLog

LIBRARY_NAMESPACE = "store_personal_libraries"
MAX_FOLDERS_PER_USER = 50
MAX_SAVED_PRODUCTS_PER_USER = 500


@dataclass(frozen=True)
class PersonalFolder:
    folder_id: UUID
    user_id: UUID
    name: str
    created_at: datetime


@dataclass(frozen=True)
class SavedProduct:
    user_id: UUID
    product_id: UUID
    folder_id: UUID | None
    saved_at: datetime


@dataclass(frozen=True)
class PersonalLibrary:
    folders: tuple[PersonalFolder, ...]
    saved_products: tuple[SavedProduct, ...]


class StoreLibraryService:
    """Persist bounded personal product references, never product snapshots."""

    def __init__(self, state_store: StateStore | None, audit_log: AuditLog) -> None:
        self._state_store = state_store or MemoryStateStore()
        self._audit_log = audit_log
        self._lock: RLock = self._state_store.authority_guard()

    def list_for_user(self, user_id: UUID) -> PersonalLibrary:
        with self._lock:
            library = self._load()
            return PersonalLibrary(
                folders=tuple(
                    sorted(
                        (folder for folder in library.folders if folder.user_id == user_id),
                        key=lambda folder: (folder.name.casefold(), str(folder.folder_id)),
                    )
                ),
                saved_products=tuple(
                    sorted(
                        (item for item in library.saved_products if item.user_id == user_id),
                        key=lambda item: item.saved_at,
                        reverse=True,
                    )
                ),
            )

    def create_folder(self, user_id: UUID, name: str) -> PersonalFolder:
        clean_name = name.strip()
        if not clean_name:
            raise AppError(422, "folder_name_required", "Enter a folder name.")
        with self._lock:
            library = self._load()
            owned = [folder for folder in library.folders if folder.user_id == user_id]
            if any(folder.name.casefold() == clean_name.casefold() for folder in owned):
                raise AppError(409, "folder_name_exists", "A folder with that name already exists.")
            if len(owned) >= MAX_FOLDERS_PER_USER:
                raise AppError(409, "folder_limit_reached", "The personal folder limit is reached.")
            folder = PersonalFolder(uuid4(), user_id, clean_name, datetime.now(UTC))
            self._commit(
                library,
                PersonalLibrary((*library.folders, folder), library.saved_products),
                "store_library_folder_created",
                str(user_id),
                {"folder_id": str(folder.folder_id)},
            )
            return folder

    def delete_folder(self, user_id: UUID, folder_id: UUID) -> None:
        with self._lock:
            library = self._load()
            folder = self._owned_folder(library, user_id, folder_id)
            folders = tuple(item for item in library.folders if item.folder_id != folder.folder_id)
            saved = tuple(
                SavedProduct(item.user_id, item.product_id, None, item.saved_at)
                if item.user_id == user_id and item.folder_id == folder_id
                else item
                for item in library.saved_products
            )
            self._commit(
                library,
                PersonalLibrary(folders, saved),
                "store_library_folder_deleted",
                str(user_id),
                {"folder_id": str(folder_id)},
            )

    def save_product(self, user_id: UUID, product_id: UUID, folder_id: UUID | None) -> SavedProduct:
        with self._lock:
            library = self._load()
            if folder_id is not None:
                self._owned_folder(library, user_id, folder_id)
            existing = next(
                (
                    item
                    for item in library.saved_products
                    if item.user_id == user_id and item.product_id == product_id
                ),
                None,
            )
            owned_count = sum(item.user_id == user_id for item in library.saved_products)
            if existing is None and owned_count >= MAX_SAVED_PRODUCTS_PER_USER:
                raise AppError(
                    409, "saved_product_limit_reached", "The saved product limit is reached."
                )
            saved_item = SavedProduct(
                user_id,
                product_id,
                folder_id,
                existing.saved_at if existing else datetime.now(UTC),
            )
            items = tuple(
                item
                for item in library.saved_products
                if not (item.user_id == user_id and item.product_id == product_id)
            )
            self._commit(
                library,
                PersonalLibrary(library.folders, (*items, saved_item)),
                "store_product_saved",
                str(user_id),
                {"product_id": str(product_id), "folder_id": str(folder_id or "")},
            )
            return saved_item

    def remove_product(self, user_id: UUID, product_id: UUID) -> None:
        with self._lock:
            library = self._load()
            exists = any(
                item.user_id == user_id and item.product_id == product_id
                for item in library.saved_products
            )
            if not exists:
                raise AppError(404, "saved_product_not_found", "Saved product not found.")
            items = tuple(
                item
                for item in library.saved_products
                if not (item.user_id == user_id and item.product_id == product_id)
            )
            self._commit(
                library,
                PersonalLibrary(library.folders, items),
                "store_product_removed",
                str(user_id),
                {"product_id": str(product_id)},
            )

    @staticmethod
    def _owned_folder(library: PersonalLibrary, user_id: UUID, folder_id: UUID) -> PersonalFolder:
        folder = next(
            (
                item
                for item in library.folders
                if item.user_id == user_id and item.folder_id == folder_id
            ),
            None,
        )
        if folder is None:
            raise AppError(404, "folder_not_found", "Folder not found.")
        return folder

    def _load(self) -> PersonalLibrary:
        payload = self._state_store.load(LIBRARY_NAMESPACE) or {}
        folders = tuple(_folder_from_payload(item) for item in payload.get("folders", []))
        saved = tuple(_saved_from_payload(item) for item in payload.get("savedProducts", []))
        return PersonalLibrary(folders, saved)

    def _save(self, library: PersonalLibrary) -> None:
        self._state_store.save(
            LIBRARY_NAMESPACE,
            {
                "folders": [_folder_payload(folder) for folder in library.folders],
                "savedProducts": [_saved_payload(item) for item in library.saved_products],
            },
        )

    def _commit(
        self,
        previous: PersonalLibrary,
        updated: PersonalLibrary,
        event_type: str,
        actor_user_id: str,
        metadata: dict[str, str],
    ) -> None:
        self._save(updated)
        try:
            self._audit_log.record(event_type, actor_user_id, metadata)
        except Exception:
            self._save(previous)
            raise


def _folder_payload(folder: PersonalFolder) -> dict[str, Any]:
    return {
        "id": str(folder.folder_id),
        "userId": str(folder.user_id),
        "name": folder.name,
        "createdAt": folder.created_at.isoformat(),
    }


def _saved_payload(item: SavedProduct) -> dict[str, Any]:
    return {
        "userId": str(item.user_id),
        "productId": str(item.product_id),
        "folderId": str(item.folder_id) if item.folder_id else None,
        "savedAt": item.saved_at.isoformat(),
    }


def _folder_from_payload(payload: dict[str, Any]) -> PersonalFolder:
    return PersonalFolder(
        UUID(str(payload["id"])),
        UUID(str(payload["userId"])),
        str(payload["name"]),
        datetime.fromisoformat(str(payload["createdAt"])),
    )


def _saved_from_payload(payload: dict[str, Any]) -> SavedProduct:
    folder_id = payload.get("folderId")
    return SavedProduct(
        UUID(str(payload["userId"])),
        UUID(str(payload["productId"])),
        UUID(str(folder_id)) if folder_id else None,
        datetime.fromisoformat(str(payload["savedAt"])),
    )
