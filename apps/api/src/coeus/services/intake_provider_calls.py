"""Immutable preparation boundary for admitted intake-provider work."""

from collections.abc import Callable
from dataclasses import dataclass, field

from coeus.services.intake import AdmittedAssistantReply


@dataclass(frozen=True)
class PreparedIntakeReply:
    """One provider decision whose execution cannot re-read provider selection."""

    requires_admission: bool
    admission_unavailable_reply: AdmittedAssistantReply
    _execute: Callable[[], AdmittedAssistantReply] = field(repr=False, compare=False)

    def execute(self) -> AdmittedAssistantReply:
        return self._execute()
