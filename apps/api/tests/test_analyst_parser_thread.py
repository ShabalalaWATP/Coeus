import asyncio
import json
import threading
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.datastructures import UploadFile

from coeus.api.dependencies import get_upload_admission
from coeus.api.routes import analyst_files
from coeus.api.routes.analyst_files import preview_product_submission
from coeus.core.config import Settings
from coeus.main import create_app
from coeus.services.product_submissions import StagedSubmissionFile
from rfi_search_helpers import login
from test_external_product_workflow import _assigned_ticket, _docx, _metadata


@pytest.mark.asyncio
async def test_analyst_document_processing_does_not_block_the_event_loop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    service = app.state.product_submission_service
    original_create = service.create
    processing_started = threading.Event()
    processing_release = threading.Event()
    processing_threads: list[int] = []

    def paused_create(*args: object, **kwargs: object) -> object:
        processing_threads.append(threading.get_ident())
        processing_started.set()
        if not processing_release.wait(timeout=10):
            raise AssertionError("test did not release document processing")
        return original_create(*args, **kwargs)

    monkeypatch.setattr(service, "create", paused_create)
    event_loop_thread = threading.get_ident()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _assigned_ticket(client, app)
        analyst = await login(client, "analyst@example.test")
        acg_id = next(
            str(acg.acg_id)
            for acg in app.state.access_services.repository.list_acgs()
            if acg.code == "ACG-EU-CYBER"
        )
        upload = asyncio.create_task(
            client.post(
                f"/api/v1/analyst/tasks/{ticket_id}/submissions/upload",
                headers={"X-CSRF-Token": str(analyst["csrfToken"])},
                files={
                    "asset": (
                        "responsive.docx",
                        _docx("MOCK DATA ONLY. Synthetic responsive processing."),
                        ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                    ),
                    "metadata": (None, json.dumps(_metadata(acg_id)), "application/json"),
                },
            )
        )
        try:
            assert await asyncio.to_thread(processing_started.wait, 5)
            health = await asyncio.wait_for(client.get("/api/v1/health/live"), timeout=2)
        finally:
            processing_release.set()
        uploaded = await upload

    assert health.status_code == 200
    assert uploaded.status_code == 201
    assert processing_threads and processing_threads[0] != event_loop_thread


@pytest.mark.asyncio
async def test_cancelled_upload_holds_admission_and_staged_file_until_worker_finishes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    admission = _RecordingAdmission()
    app.dependency_overrides[get_upload_admission] = lambda: admission
    service = app.state.product_submission_service
    processing_started = threading.Event()
    processing_release = threading.Event()
    staged_files: list[StagedSubmissionFile] = []
    create_calls = 0

    def paused_create(*args: object, **_kwargs: object) -> None:
        nonlocal create_calls
        create_calls += 1
        staged = args[-1]
        assert isinstance(staged, StagedSubmissionFile)
        staged_files.append(staged)
        processing_started.set()
        if not processing_release.wait(timeout=10):
            raise AssertionError("test did not release document processing")
        assert staged.path.exists()
        assert staged.path.read_bytes()

    monkeypatch.setattr(service, "create", paused_create)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _assigned_ticket(client, app)
        analyst = await login(client, "analyst@example.test")
        acg_id = next(
            str(acg.acg_id)
            for acg in app.state.access_services.repository.list_acgs()
            if acg.code == "ACG-EU-CYBER"
        )
        upload = asyncio.create_task(
            client.post(
                f"/api/v1/analyst/tasks/{ticket_id}/submissions/upload",
                headers={"X-CSRF-Token": str(analyst["csrfToken"])},
                files={
                    "asset": (
                        "cancelled.docx",
                        _docx("MOCK DATA ONLY. Synthetic cancelled processing."),
                        ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                    ),
                    "metadata": (None, json.dumps(_metadata(acg_id)), "application/json"),
                },
            )
        )
        assert await asyncio.to_thread(processing_started.wait, 5)
        upload.cancel()
        await asyncio.sleep(0)
        upload.cancel()
        await asyncio.sleep(0)

        assert not upload.done()
        assert admission.active == 1
        assert staged_files[0].path.exists()

        processing_release.set()
        with pytest.raises(asyncio.CancelledError):
            await upload

    assert admission.active == 0
    assert not staged_files[0].path.exists()
    assert create_calls == 1
    assert not any((tmp_path / "objects").rglob("*"))


@pytest.mark.asyncio
async def test_cancelled_upload_holds_admission_until_staging_thread_is_cleaned(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    admission = _RecordingAdmission()
    app.dependency_overrides[get_upload_admission] = lambda: admission
    original_stage = analyst_files._stage_file
    staging_started = threading.Event()
    staging_release = threading.Event()
    staged_files: list[StagedSubmissionFile] = []
    create_calls = 0

    def paused_stage(*args: object) -> StagedSubmissionFile:
        staged = original_stage(*args)
        staged_files.append(staged)
        staging_started.set()
        if not staging_release.wait(timeout=10):
            raise AssertionError("test did not release file staging")
        assert staged.path.exists()
        assert staged.path.read_bytes()
        return staged

    def unexpected_create(*_args: object, **_kwargs: object) -> None:
        nonlocal create_calls
        create_calls += 1

    monkeypatch.setattr(analyst_files, "_stage_file", paused_stage)
    monkeypatch.setattr(app.state.product_submission_service, "create", unexpected_create)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _assigned_ticket(client, app)
        analyst = await login(client, "analyst@example.test")
        acg_id = next(
            str(acg.acg_id)
            for acg in app.state.access_services.repository.list_acgs()
            if acg.code == "ACG-EU-CYBER"
        )
        upload = asyncio.create_task(
            client.post(
                f"/api/v1/analyst/tasks/{ticket_id}/submissions/upload",
                headers={"X-CSRF-Token": str(analyst["csrfToken"])},
                files={
                    "asset": (
                        "cancelled-staging.docx",
                        _docx("MOCK DATA ONLY. Synthetic cancelled staging."),
                        ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
                    ),
                    "metadata": (None, json.dumps(_metadata(acg_id)), "application/json"),
                },
            )
        )
        assert await asyncio.to_thread(staging_started.wait, 5)
        upload.cancel()
        await asyncio.sleep(0)
        upload.cancel()
        await asyncio.sleep(0)

        assert not upload.done()
        assert admission.active == 1
        assert staged_files[0].path.exists()

        staging_release.set()
        with pytest.raises(asyncio.CancelledError):
            await upload

    assert admission.active == 0
    assert not staged_files[0].path.exists()
    assert create_calls == 0
    assert not any((tmp_path / "objects").rglob("*"))


@pytest.mark.asyncio
async def test_staged_file_is_cleaned_when_multipart_context_exit_is_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    staged_files: list[StagedSubmissionFile] = []
    original_stage = analyst_files._stage_file

    def recording_stage(*args: object) -> StagedSubmissionFile:
        staged = original_stage(*args)
        staged_files.append(staged)
        return staged

    class CancellingFormContext:
        async def __aenter__(self) -> dict[str, object]:
            return {
                "metadata": json.dumps(_metadata(str(uuid4()))),
                "asset": UploadFile(
                    BytesIO(_docx("MOCK DATA ONLY. Synthetic context cancellation.")),
                    filename="context-cancelled.docx",
                ),
            }

        async def __aexit__(self, *_args: object) -> None:
            raise asyncio.CancelledError

    class RequestWithCancellingForm:
        def form(self, **_kwargs: object) -> CancellingFormContext:
            return CancellingFormContext()

    monkeypatch.setattr(analyst_files, "install_receive_limit", lambda *_args: None)
    monkeypatch.setattr(analyst_files, "_stage_file", recording_stage)

    with pytest.raises(asyncio.CancelledError):
        await analyst_files._stage_request(RequestWithCancellingForm(), 1_000_000)

    assert len(staged_files) == 1
    assert not staged_files[0].path.exists()


@pytest.mark.asyncio
async def test_submission_worker_cancellation_is_propagated() -> None:
    from coeus.api.routes.analyst_files import _run_submission_create

    def cancelled_worker() -> None:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await _run_submission_create(cancelled_worker)


@pytest.mark.asyncio
async def test_binary_product_preview_preserves_bounded_content_type() -> None:
    asset = SimpleNamespace(
        preview_kind="binary",
        detected_mime_type="application/pdf",
    )
    drafts = SimpleNamespace(
        preview=lambda *_args: SimpleNamespace(asset=asset, content=b"synthetic")
    )
    response = await preview_product_submission(
        uuid4(),
        uuid4(),
        uuid4(),
        SimpleNamespace(user=object()),
        drafts,
    )

    assert response.body == b"synthetic"
    assert response.media_type == "application/pdf"


class _RecordingAdmission:
    def __init__(self) -> None:
        self.active = 0

    def reserve(self, _principal_id: object, _units: int) -> "_RecordingReservation":
        return _RecordingReservation(self)


class _RecordingReservation:
    def __init__(self, admission: _RecordingAdmission) -> None:
        self._admission = admission

    def __enter__(self) -> None:
        self._admission.active += 1

    def __exit__(self, *_args: object) -> None:
        self._admission.active -= 1
