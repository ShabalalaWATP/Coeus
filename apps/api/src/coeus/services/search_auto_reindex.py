"""Debounced local coordinator for automatic shadow-generation rebuilds."""

import asyncio
from contextlib import suppress
from threading import Lock
from uuid import UUID

from coeus.core.errors import AppError
from coeus.core.logging import get_logger
from coeus.services.search_configuration import SearchConfigurationService
from coeus.services.search_indexing import SearchIndexingService

SYSTEM_REINDEX_ACTOR = UUID("00000000-0000-0000-0000-000000000001")
logger = get_logger(__name__)


class SearchAutoReindexService:
    def __init__(
        self,
        configuration: SearchConfigurationService,
        indexing: SearchIndexingService,
        *,
        enabled: bool,
        debounce_seconds: float,
    ) -> None:
        self._configuration = configuration
        self._indexing = indexing
        self._enabled = enabled
        self._debounce_seconds = debounce_seconds
        self._queued = False
        self._lock = Lock()

    def enqueue(self) -> None:
        if not self._enabled:
            return
        with self._lock:
            self._queued = True

    async def run(self, stop: asyncio.Event) -> None:
        if not self._enabled:
            return
        self.enqueue()
        while not stop.is_set():
            if not self._take_queued():
                with suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=0.25)
                continue
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=self._debounce_seconds)
            if stop.is_set():
                return
            await self._rebuild_if_required()

    async def _rebuild_if_required(self) -> None:
        state = self._configuration.state()
        if state.index_status == "indexing":
            self.enqueue()
            return
        if state.index_status == "ready" and state.degraded_reason is None:
            return
        try:
            profile = self._indexing.start(SYSTEM_REINDEX_ACTOR)
            await asyncio.to_thread(self._indexing.run, profile)
        except AppError as exc:
            if exc.code == "search_reindex_active":
                self.enqueue()
                return
            logger.warning("automatic_search_reindex_rejected", extra={"reason": exc.code})
        except Exception:
            logger.exception("automatic_search_reindex_failed")
        finally:
            state = self._configuration.state()
            if state.index_status == "stale" or state.degraded_reason == "corpus_changed":
                self.enqueue()

    def _take_queued(self) -> bool:
        with self._lock:
            queued = self._queued
            self._queued = False
        return queued
