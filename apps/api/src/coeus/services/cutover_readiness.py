"""Fail-closed cutover-readiness reporting."""

from coeus.application.ports.cutover_readiness import CutoverReadinessStore
from coeus.domain.cutover_readiness import (
    CutoverCheckCode,
    CutoverCheckStatus,
    CutoverReadinessCheck,
    CutoverReadinessReport,
)

DATABASE_CODES = tuple(CutoverCheckCode)[:11]
EXTERNAL_CODES = tuple(CutoverCheckCode)[11:]


class CutoverReadinessService:
    def __init__(self, store: CutoverReadinessStore) -> None:
        self._store = store

    def report(self) -> CutoverReadinessReport:
        try:
            database_checks = self._store.inspect()
            if tuple(item.code for item in database_checks) != DATABASE_CODES:
                raise ValueError("cutover readiness evidence is incomplete")
        except Exception:
            database_checks = tuple(
                CutoverReadinessCheck(code, CutoverCheckStatus.ERROR, 0, 1)
                for code in DATABASE_CODES
            )
        external_checks = tuple(
            CutoverReadinessCheck(code, CutoverCheckStatus.BLOCKED, 0, 1) for code in EXTERNAL_CODES
        )
        checks = (*database_checks, *external_checks)
        return CutoverReadinessReport(
            ready=all(item.status is CutoverCheckStatus.PASSED for item in checks),
            checks=checks,
        )
