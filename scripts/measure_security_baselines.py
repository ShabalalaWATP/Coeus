"""Reproducible synthetic baselines for the Sprint 17 hardening gates."""

from __future__ import annotations

import json
import ctypes
import tempfile
import time
import tracemalloc
from io import BytesIO
from threading import Event, Thread
from uuid import uuid4

from fastapi.testclient import TestClient

from coeus.api.routes.store_files import _stage_upload
from coeus.core.config import Settings
from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.main import create_app
from coeus.persistence.state_store import MemoryStateStore
from coeus.repositories.tickets import InMemoryTicketRepository

UPLOAD_BYTES = 10_000_000


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("page_fault_count", ctypes.c_ulong),
        ("peak_working_set_size", ctypes.c_size_t),
        ("working_set_size", ctypes.c_size_t),
        ("quota_peak_paged_pool_usage", ctypes.c_size_t),
        ("quota_paged_pool_usage", ctypes.c_size_t),
        ("quota_peak_non_paged_pool_usage", ctypes.c_size_t),
        ("quota_non_paged_pool_usage", ctypes.c_size_t),
        ("pagefile_usage", ctypes.c_size_t),
        ("peak_pagefile_usage", ctypes.c_size_t),
    ]


def _working_set_bytes() -> int:
    counters = _ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    process = kernel32.GetCurrentProcess()
    get_memory = psapi.GetProcessMemoryInfo
    get_memory.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_ProcessMemoryCounters),
        ctypes.c_ulong,
    ]
    get_memory.restype = ctypes.c_int
    result = get_memory(process, ctypes.byref(counters), counters.cb)
    if not result:
        raise RuntimeError("Could not sample the process working set.")
    return int(counters.working_set_size)


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * percentile))
    return round(ordered[index], 3)


def request_latency() -> dict[str, float]:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    values: list[float] = []
    with TestClient(app) as client:
        for _index in range(30):
            started = time.perf_counter()
            response = client.get("/api/v1/health/live")
            response.raise_for_status()
            values.append((time.perf_counter() - started) * 1_000)
    return {"p50Ms": _percentile(values, 0.5), "p95Ms": _percentile(values, 0.95)}


def staged_upload() -> dict[str, float | int]:
    content = b"x" * UPLOAD_BYTES
    timings: list[float] = []
    peak_bytes = 0
    peak_working_set_delta = 0
    staged_size = 0
    for _index in range(5):
        tracemalloc.start()
        stop_sampling = Event()
        working_set_samples = [_working_set_bytes()]

        def sample_working_set() -> None:
            while not stop_sampling.wait(0.001):
                working_set_samples.append(_working_set_bytes())

        sampler = Thread(target=sample_working_set)
        sampler.start()
        started = time.perf_counter()
        staged = _stage_upload(
            BytesIO(content), "synthetic.bin", "application/octet-stream", UPLOAD_BYTES
        )
        timings.append((time.perf_counter() - started) * 1_000)
        stop_sampling.set()
        sampler.join()
        working_set_samples.append(_working_set_bytes())
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_bytes = max(peak_bytes, peak)
        peak_working_set_delta = max(
            peak_working_set_delta,
            max(working_set_samples) - working_set_samples[0],
        )
        staged_size = staged.path.stat().st_size
        staged.path.unlink(missing_ok=True)
    return {
        "inputBytes": UPLOAD_BYTES,
        "peakPythonHeapBytes": peak_bytes,
        "peakWorkingSetDeltaBytes": peak_working_set_delta,
        "temporaryBytes": staged_size,
        "p50Ms": _percentile(timings, 0.5),
        "p95Ms": _percentile(timings, 0.95),
    }


def _ticket(index: int) -> TicketRecord:
    return TicketRecord(
        ticket_id=uuid4(),
        reference=f"TCK-BENCH-{index:05d}",
        requester_user_id=uuid4(),
        state=TicketState.DRAFT_INTAKE,
        intake=IntakeDetails(title=f"Synthetic ticket {index}"),
    )


def ticket_mutation(count: int) -> float:
    state = MemoryStateStore()
    repository = InMemoryTicketRepository(state)
    tickets = tuple(_ticket(index) for index in range(count))
    repository._tickets = {ticket.ticket_id: ticket for ticket in tickets}
    started = time.perf_counter()
    repository.save(tickets[-1])
    return round((time.perf_counter() - started) * 1_000, 3)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="coeus-baseline-"):
        mutation = {"10": ticket_mutation(10), "10000": ticket_mutation(10_000)}
        results = {
            "fixture": "synthetic-mock-only",
            "healthLatency": request_latency(),
            "stagedUpload": staged_upload(),
            "ticketMutationMs": mutation,
            "embeddingCallBudget": {"candidateCorpus": 101, "maximumCalls": 33},
        }
    results["ticketMutationRatio"] = round(mutation["10000"] / mutation["10"], 2)
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
