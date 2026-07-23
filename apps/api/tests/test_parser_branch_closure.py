import asyncio
from collections.abc import Coroutine

import pytest
from pypdf.generic import ArrayObject, NameObject

from coeus.api.routes import analyst_files
from coeus.core.errors import AppError
from coeus.services import office_archive, pdf_decode_budget


@pytest.mark.asyncio
async def test_staging_rejects_a_form_without_required_parts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class EmptyFormContext:
        async def __aenter__(self) -> dict[str, object]:
            return {}

        async def __aexit__(self, *_args: object) -> None:
            return None

    class EmptyFormRequest:
        def form(self, **_kwargs: object) -> EmptyFormContext:
            return EmptyFormContext()

    monkeypatch.setattr(analyst_files, "install_receive_limit", lambda *_args: None)

    with pytest.raises(AppError, match="Upload form is invalid"):
        await analyst_files._stage_request(EmptyFormRequest(), 1_000)


def test_staging_preserves_an_open_failure_before_a_path_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failed_temp_file(**_kwargs: object) -> object:
        raise OSError("synthetic open failure")

    monkeypatch.setattr(analyst_files, "NamedTemporaryFile", failed_temp_file)

    with pytest.raises(OSError, match="synthetic open failure"):
        analyst_files._stage_file(object(), "synthetic.pdf", "application/pdf", 1_000)


def test_pdf_content_array_ignores_non_stream_items_but_charges_separator() -> None:
    budget = pdf_decode_budget._PdfStreamBudget()

    decoded = budget._decode_content(ArrayObject([NameObject("/Ignored")]))

    assert decoded == b"\n"
    assert budget.decoded_total == 1


def test_office_eocd_search_handles_empty_input_and_a_false_signature_candidate() -> None:
    with pytest.raises(office_archive.OfficeArchiveInvalidError, match="end record"):
        office_archive._find_eocd(b"")

    malformed = office_archive._EOCD.pack(
        b"PK\x05\x06",
        0,
        0,
        0,
        0,
        0,
        0,
        1,
    )
    with pytest.raises(office_archive.OfficeArchiveInvalidError, match="end record"):
        office_archive._find_eocd(malformed)


@pytest.mark.asyncio
async def test_cancelled_protected_thread_retrieves_a_completed_worker_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailedWorker:
        def done(self) -> bool:
            return True

        def cancelled(self) -> bool:
            return False

        def result(self) -> None:
            raise RuntimeError("synthetic worker failure")

    def completed_task(coroutine: Coroutine[object, object, object]) -> FailedWorker:
        coroutine.close()
        return FailedWorker()

    async def cancelled_shield(_worker: object) -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(analyst_files.asyncio, "create_task", completed_task)
    monkeypatch.setattr(analyst_files.asyncio, "shield", cancelled_shield)
    with pytest.raises(asyncio.CancelledError):
        await analyst_files._run_protected_thread(lambda: None)
