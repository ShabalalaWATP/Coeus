"""Shared bounded synchronous HTTP transport primitives for provider integrations."""

import socket
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress

import httpx


@contextmanager
def total_deadline_client(timeout: float) -> Iterator[tuple[httpx.Client, "TotalDeadline"]]:
    """Yield a client whose complete operation cannot outlive ``timeout``."""
    if timeout <= 0:
        raise ValueError("The provider timeout must be positive.")
    expires_at = time.monotonic() + timeout
    client = httpx.Client(timeout=timeout)
    remaining = expires_at - time.monotonic()
    if remaining <= 0:
        _close_client(client)
        raise httpx.ReadTimeout("The provider response exceeded its total deadline.")
    deadline = TotalDeadline(expires_at, remaining, lambda: _close_client(client))
    with client:
        deadline.start()
        try:
            yield client, deadline
            deadline.check()
        except httpx.HTTPError as exc:
            if deadline.expired:
                raise deadline.error() from exc
            raise
        finally:
            deadline.stop()


class TotalDeadline:
    """Monotonic deadline that interrupts each active transport generation once."""

    def __init__(
        self,
        expires_at: float,
        remaining: float,
        close: Callable[[], None],
    ) -> None:
        self._expires_at = expires_at
        self._expired = threading.Event()
        self._close = close
        self._close_generation = 0
        self._interrupted_generation = -1
        self._close_lock = threading.Lock()
        self._timer = threading.Timer(remaining, self._expire)
        self._timer.daemon = True

    @property
    def expired(self) -> bool:
        return self._expired.is_set() or time.monotonic() >= self._expires_at

    def bind_response(self, response: httpx.Response, client: httpx.Client) -> None:
        """Make the watchdog interrupt the active response instead of client setup."""
        self._bind_interrupt(lambda: _interrupt_response(response, client))

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.cancel()
        self._timer.join()

    def check(self) -> None:
        if self.expired:
            self._expired.set()
            self._interrupt()
            raise self.error()

    def error(self) -> httpx.ReadTimeout:
        return httpx.ReadTimeout("The provider response exceeded its total deadline.")

    def _bind_interrupt(self, close: Callable[[], None]) -> None:
        with self._close_lock:
            self._close = close
            self._close_generation += 1
            expired = self._expired.is_set() or time.monotonic() >= self._expires_at
            if expired:
                self._expired.set()
        if expired:
            self._interrupt()

    def _expire(self) -> None:
        self._expired.set()
        self._interrupt()

    def _interrupt(self) -> None:
        with self._close_lock:
            if self._interrupted_generation == self._close_generation:
                return
            self._interrupted_generation = self._close_generation
            close = self._close
        close()


def _close_client(client: httpx.Client) -> None:
    """Close real HTTPX clients while retaining lightweight test adapters."""
    close = getattr(client, "close", None)
    if close is not None:
        close()


def _interrupt_response(response: httpx.Response, client: httpx.Client) -> None:
    """Interrupt a blocking read without waiting on HTTPX's pool lock."""
    extensions = getattr(response, "extensions", {})
    network_stream = extensions.get("network_stream")
    get_extra_info = getattr(network_stream, "get_extra_info", None)
    response_socket = get_extra_info("socket") if get_extra_info is not None else None
    shutdown = getattr(response_socket, "shutdown", None)
    if shutdown is None:
        _close_client(client)
        return
    with suppress(OSError):
        shutdown(socket.SHUT_RDWR)
