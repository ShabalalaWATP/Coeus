"""Regression coverage for pre-auth parsing and aggregate upload admission."""

import json
from collections.abc import AsyncIterator
from io import BytesIO
from pathlib import Path
from tempfile import SpooledTemporaryFile
from uuid import uuid4

import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient

from coeus.api.routes.store_files import CHUNK_SIZE, _stage_upload
from coeus.api.upload_limits import UploadWireLimitExceeded, install_receive_limit
from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.main import create_app
from coeus.services.upload_admission import UploadAdmissionController
from store_api_helpers import login, product_payload
from test_external_product_workflow import _assigned_ticket, _metadata


@pytest.mark.asyncio
@pytest.mark.parametrize("authenticated", [False, True])
async def test_security_rejection_happens_before_multipart_spooling(
    authenticated: bool,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    created_spools: list[object] = []

    def recording_spool(*args: object, **kwargs: object) -> object:
        spool = SpooledTemporaryFile(*args, **kwargs)  # noqa: SIM115 - parser owns it.
        created_spools.append(spool)
        return spool

    monkeypatch.setattr("starlette.formparsers.SpooledTemporaryFile", recording_spool)
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    acg_id = str(app.state.access_services.repository.list_acgs()[0].acg_id)
    metadata = product_payload(acg_id)
    metadata.pop("assets")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        if authenticated:
            await login(client, "admin@example.test")
        response = await client.post(
            "/api/v1/store/products/upload",
            files={
                "asset": ("blocked.txt", b"blocked bytes", "text/plain"),
                "metadata": (None, json.dumps(metadata), "application/json"),
            },
        )

    assert response.status_code in {401, 403}
    assert created_spools == []


@pytest.mark.asyncio
async def test_store_permission_rejection_precedes_multipart_spooling(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    created_spools: list[object] = []

    def recording_spool(*args: object, **kwargs: object) -> object:
        spool = SpooledTemporaryFile(*args, **kwargs)  # noqa: SIM115 - parser owns it.
        created_spools.append(spool)
        return spool

    monkeypatch.setattr("starlette.formparsers.SpooledTemporaryFile", recording_spool)
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    acg_id = str(app.state.access_services.repository.list_acgs()[0].acg_id)
    metadata = product_payload(acg_id)
    metadata.pop("assets")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "user@example.test")
        response = await client.post(
            "/api/v1/store/products/upload",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            files={
                "asset": ("blocked.bin", b"blocked bytes", "application/octet-stream"),
                "metadata": (None, json.dumps(metadata), "application/json"),
            },
        )

    assert response.status_code == 403
    assert created_spools == []


@pytest.mark.asyncio
async def test_content_length_free_body_stops_at_receive_budget(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        argon2_memory_cost=8_192,
        local_object_storage_path=str(tmp_path / "objects"),
        local_upload_max_bytes=32,
        upload_max_inflight_bytes=64,
    )
    app = create_app(settings)
    acg_id = str(app.state.access_services.repository.list_acgs()[0].acg_id)
    metadata = product_payload(acg_id)
    metadata.pop("assets")
    boundary = "coeus-security-boundary"
    body = _multipart_body(boundary, json.dumps(metadata), b"x" * (300 * 1024))
    before = len(app.state.store_services.repository.list_products())

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        response = await client.post(
            "/api/v1/store/products/upload",
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "X-CSRF-Token": str(session["csrfToken"]),
            },
            content=_body_chunks(body),
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "asset_too_large"
    assert len(app.state.store_services.repository.list_products()) == before
    assert not any((tmp_path / "objects").rglob("*"))


@pytest.mark.asyncio
async def test_analyst_content_length_free_body_stops_before_unbounded_spooling(
    tmp_path: Path,
) -> None:
    settings = Settings(
        environment="test",
        argon2_memory_cost=8_192,
        local_object_storage_path=str(tmp_path / "objects"),
        local_upload_max_bytes=32,
        upload_max_inflight_bytes=64,
    )
    app = create_app(settings)
    boundary = "coeus-analyst-security-boundary"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _assigned_ticket(client, app)
        session = await login(client, "analyst@example.test")
        acg_id = str(app.state.access_services.repository.list_acgs()[0].acg_id)
        body = _multipart_body(boundary, json.dumps(_metadata(acg_id)), b"x" * (300 * 1024))
        response = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/submissions/upload",
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "X-CSRF-Token": str(session["csrfToken"]),
            },
            content=_body_chunks(body),
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "asset_too_large"


@pytest.mark.asyncio
async def test_multichunk_upload_streams_to_storage_and_preserves_bytes(tmp_path: Path) -> None:
    content = b"\x89PNG\r\n\x1a\n" + b"M" * (CHUNK_SIZE * 2 + 17)
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
            local_upload_max_bytes=len(content) + 1,
            upload_max_inflight_bytes=(len(content) + 1) * 2,
        )
    )
    acg_id = str(app.state.access_services.repository.list_acgs()[0].acg_id)
    metadata = product_payload(acg_id)
    metadata.pop("assets")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        created = await client.post(
            "/api/v1/store/products/upload",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            files={
                "asset": ("streamed.png", content, "image/png"),
                "metadata": (None, json.dumps(metadata), "application/json"),
            },
        )
        product = created.json()
        asset = product["assets"][0]
        grant = await client.get(
            f"/api/v1/store/products/{product['id']}/assets/{asset['id']}/access"
        )
        downloaded = await client.get(
            f"/api/v1/store/products/{product['id']}/assets/{asset['id']}/download",
            headers={"X-Asset-Token": grant.json()["downloadToken"]},
        )

    assert created.status_code == 201
    assert asset["sizeBytes"] == len(content)
    assert downloaded.status_code == 200
    assert downloaded.content == content


@pytest.mark.asyncio
async def test_upload_rejects_incomplete_multipart_form(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        response = await client.post(
            "/api/v1/store/products/upload",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            files={"asset": ("incomplete.bin", b"bytes", "application/octet-stream")},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "product_upload_invalid"


@pytest.mark.parametrize("declared", ["invalid", "-1", str(1024 * 1024)])
def test_receive_limit_rejects_invalid_or_oversized_declared_lengths(declared: str) -> None:
    request = Request(
        {"type": "http", "headers": [(b"content-length", declared.encode())]},
        receive=lambda: None,
    )

    expected = AppError if declared in {"invalid", "-1"} else UploadWireLimitExceeded
    with pytest.raises(expected):
        install_receive_limit(request, 10)


@pytest.mark.asyncio
async def test_receive_limit_preserves_non_body_asgi_messages() -> None:
    async def disconnect() -> dict[str, str]:
        return {"type": "http.disconnect"}

    request = Request({"type": "http", "headers": []}, receive=disconnect)
    install_receive_limit(request, 1)

    assert await request._receive() == {"type": "http.disconnect"}


def test_staging_failure_before_file_creation_has_no_cleanup_side_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "coeus.api.routes.store_files.NamedTemporaryFile",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("temporary storage unavailable")),
    )

    with pytest.raises(OSError, match="unavailable"):
        _stage_upload(BytesIO(b"synthetic"), "asset.bin", 20)


def test_upload_admission_releases_capacity_after_rejection() -> None:
    controller = UploadAdmissionController(
        max_concurrent=1,
        max_per_user=1,
        max_inflight_bytes=10,
    )
    first_user = uuid4()

    with (
        controller.reserve(first_user, 10),
        pytest.raises(AppError, match="upload_capacity_exceeded"),
        controller.reserve(uuid4(), 1),
    ):
        pass

    with controller.reserve(first_user, 10):
        pass


def test_upload_reservation_renewal_requires_an_active_context() -> None:
    controller = UploadAdmissionController(
        max_concurrent=1,
        max_per_user=1,
        max_inflight_bytes=1,
    )
    reservation = controller.reserve(uuid4(), 1)

    with pytest.raises(RuntimeError, match="inactive"):
        reservation.renew()
    reservation.__enter__()
    reservation.renew()
    reservation.__exit__(None, None, None)
    reservation.__exit__(None, None, None)


def test_upload_admission_tracks_multiple_reservations_for_one_principal() -> None:
    controller = UploadAdmissionController(
        max_concurrent=2,
        max_per_user=2,
        max_inflight_bytes=2,
    )
    principal = uuid4()

    with controller.reserve(principal), controller.reserve(principal):
        pass


async def _body_chunks(body: bytes) -> AsyncIterator[bytes]:
    for offset in range(0, len(body), 16 * 1024):
        yield body[offset : offset + 16 * 1024]


def _multipart_body(boundary: str, metadata: str, content: bytes) -> bytes:
    return (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="metadata"\r\n'
            "Content-Type: application/json\r\n\r\n"
            f"{metadata}\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="asset"; filename="large.bin"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        + content
        + f"\r\n--{boundary}--\r\n".encode()
    )
