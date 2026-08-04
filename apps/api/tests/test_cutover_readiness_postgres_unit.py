"""Unit coverage for bounded readiness evidence conversion."""

from coeus.domain.cutover_readiness import CutoverCheckCode, CutoverCheckStatus
from coeus.persistence.cutover_readiness_postgres import _checks


def test_evidence_conversion_requires_exact_safe_counts() -> None:
    values = {code: 0 for code in tuple(CutoverCheckCode)[:11]}
    values.update(
        {
            CutoverCheckCode.MIGRATION_HEAD: 1,
            CutoverCheckCode.IDENTITY_PROJECTION: 1,
            CutoverCheckCode.ROUTING_LEAF_COVERAGE: 7,
            CutoverCheckCode.ROUTING_CAPABILITY_MAPPINGS: 40,
            CutoverCheckCode.JIOC_SERVICE_GRANT: 1,
        }
    )
    assert all(item.status is CutoverCheckStatus.PASSED for item in _checks(values))
    values[CutoverCheckCode.PACKAGE_INTEGRITY] = 2
    blocked = _checks(values)
    assert blocked[6].status is CutoverCheckStatus.BLOCKED
    assert blocked[6].observed_count == 2
