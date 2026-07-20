import json
from io import BytesIO
from uuid import uuid4

import pytest

from coeus.api.routes import analyst_files
from coeus.api.routes.analyst_files import (
    _metadata,
    _stage_file,
    _validate_metadata,
)
from coeus.core.errors import AppError


def _payload() -> dict[str, object]:
    return {
        "title": "Synthetic assessment",
        "summary": "MOCK DATA ONLY assessment.",
        "description": "Synthetic description.",
        "productType": "assessment",
        "sourceType": "analyst_submission",
        "ownerTeam": "RFA",
        "areaOrRegion": "Test region",
        "classificationLevel": 1,
        "releasability": [" MOCK ", "MOCK"],
        "handlingCaveats": ["MOCK DATA ONLY"],
        "tags": [" Alpha ", "alpha", ""],
        "acgIds": [str(uuid4())],
        "timePeriodStart": "2026-07-01",
        "timePeriodEnd": "2026-07-31",
    }


def test_stages_file_with_sanitised_name_hash_and_size(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(analyst_files, "NamedTemporaryFile", _temporary_file_factory(tmp_path))
    staged = _stage_file(BytesIO(b"synthetic"), "../report.pdf", "application/pdf", 20)

    assert staged.name == "report.pdf"
    assert staged.declared_mime_type == "application/pdf"
    assert staged.size_bytes == 9
    assert len(staged.sha256) == 64
    staged.path.unlink()


def test_staging_rejects_empty_and_oversized_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(analyst_files, "NamedTemporaryFile", _temporary_file_factory(tmp_path))
    with pytest.raises(AppError, match="asset_empty"):
        _stage_file(BytesIO(b""), "empty.pdf", "application/pdf", 20)
    with pytest.raises(AppError, match="asset_too_large"):
        _stage_file(BytesIO(b"too large"), "large.pdf", "application/pdf", 2)
    assert list(tmp_path.iterdir()) == []


def test_metadata_is_validated_and_normalised() -> None:
    payload = _validate_metadata(json.dumps(_payload()))
    metadata = _metadata(payload)

    assert metadata.tags == ("alpha",)
    assert metadata.releasability == ("MOCK",)
    assert metadata.handling_caveats == ("MOCK DATA ONLY",)


@pytest.mark.parametrize("raw", ["not-json", json.dumps({"title": "no"})])
def test_metadata_rejects_invalid_documents(raw: str) -> None:
    with pytest.raises(AppError, match="product_metadata_invalid"):
        _validate_metadata(raw)


def test_metadata_rejects_oversized_or_unsupported_release_markers(monkeypatch) -> None:
    monkeypatch.setattr(analyst_files, "MAX_METADATA_BYTES", 2)
    with pytest.raises(AppError, match="product_metadata_invalid"):
        _validate_metadata("{ }")

    payload = _payload()
    payload["releasability"] = ["NOT-ALLOWED"]
    model = analyst_files.ProductSubmissionMetadataRequest.model_validate(payload)
    with pytest.raises(AppError, match="release_markers_unsupported"):
        _metadata(model)


def _temporary_file_factory(tmp_path):
    counter = 0

    def factory(**_kwargs):
        nonlocal counter
        counter += 1
        return (tmp_path / f"stage-{counter}").open("w+b")

    return factory
