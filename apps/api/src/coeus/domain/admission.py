"""Policy values for staged scarce-resource admission."""

from enum import StrEnum


class AdmissionMode(StrEnum):
    """Increasing enforcement levels used during controlled rollout."""

    OBSERVE = "observe"
    DEPLOYMENT = "deployment"
    PRINCIPAL = "principal"


def admission_denial_scope(
    mode: AdmissionMode,
    *,
    deployment_exceeded: bool,
    principal_exceeded: bool,
) -> str | None:
    """Return the enforced denial scope, or ``None`` when work may proceed."""
    if mode is AdmissionMode.OBSERVE:
        return None
    if deployment_exceeded:
        return "deployment"
    if mode is AdmissionMode.PRINCIPAL and principal_exceeded:
        return "principal"
    return None
