"""Application boundary for bounded cutover-readiness evidence."""

from typing import Protocol

from coeus.domain.cutover_readiness import CutoverReadinessCheck


class CutoverReadinessStore(Protocol):
    def inspect(self) -> tuple[CutoverReadinessCheck, ...]: ...
