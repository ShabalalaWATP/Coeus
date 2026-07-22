from datetime import UTC, datetime
from uuid import uuid4

from coeus.domain.product_submission import DraftProductAsset, DraftProductVersion
from coeus.services.qc_proofing import MAX_FINDINGS, proofing_findings


def _draft(*, content: str, assets: tuple[DraftProductAsset, ...] = ()) -> DraftProductVersion:
    return DraftProductVersion(
        version_id=uuid4(),
        ticket_id=uuid4(),
        version_number=1,
        title="Synthetic assessment",
        summary="MOCK DATA ONLY summary.",
        product_type="assessment",
        content=content,
        assets=assets,
        created_by_user_id=uuid4(),
        created_at=datetime.now(UTC),
        description="Synthetic description.",
    )


def test_finds_spelling_case_and_repeated_words() -> None:
    findings = proofing_findings(
        _draft(content="INTELIGENCE Inteligence inteligence movement movement")
    )

    assert [(item.original_text, item.suggested_text) for item in findings[:3]] == [
        ("INTELIGENCE", "INTELLIGENCE"),
        ("Inteligence", "Intelligence"),
        ("inteligence", "intelligence"),
    ]
    assert any(
        item.category == "grammar" and item.original_text == "movement movement"
        for item in findings
    )


def test_flags_image_text_as_not_automatically_proofed() -> None:
    image = DraftProductAsset(
        uuid4(),
        "annotated-map.png",
        "png",
        "image/png",
        20,
        "a" * 64,
        detected_mime_type="image/png",
        preview_kind="image",
        processing_status="ready",
    )

    findings = proofing_findings(_draft(content="MOCK DATA ONLY narrative.", assets=(image,)))

    coverage = next(item for item in findings if item.category == "proofing_coverage")
    assert coverage.original_text == "annotated-map.png"
    assert "could not inspect words" in coverage.detail


def test_caps_proofing_output() -> None:
    findings = proofing_findings(_draft(content=" ".join(["recieve"] * (MAX_FINDINGS + 10))))

    assert len(findings) == MAX_FINDINGS
