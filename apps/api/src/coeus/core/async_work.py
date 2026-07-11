"""Bounded offload for synchronous local/provider search work."""

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from coeus.core.errors import AppError

SEARCH_WORKERS = 2
SEARCH_WORK_TIMEOUT_SECONDS = 65.0

_executor = ThreadPoolExecutor(max_workers=SEARCH_WORKERS, thread_name_prefix="coeus-search")
_slots = asyncio.Semaphore(SEARCH_WORKERS)


async def run_bounded_search[**P, T](
    function: Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> T:
    """Run synchronous work without blocking the event loop or an unbounded queue."""
    try:
        await asyncio.wait_for(_slots.acquire(), timeout=SEARCH_WORK_TIMEOUT_SECONDS)
    except TimeoutError as exc:
        raise _unavailable() from exc

    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(_executor, partial(function, *args, **kwargs))
    future.add_done_callback(lambda _future: _slots.release())
    try:
        return await asyncio.wait_for(asyncio.shield(future), timeout=SEARCH_WORK_TIMEOUT_SECONDS)
    except TimeoutError as exc:
        # The worker retains its slot until it actually finishes, preventing a
        # timed-out provider call from freeing capacity and growing the queue.
        raise _unavailable() from exc


def _unavailable() -> AppError:
    return AppError(503, "search_work_timeout", "Search work did not complete in time.")
