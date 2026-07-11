from enum import StrEnum


class TicketState(StrEnum):
    DRAFT_INTAKE = "DRAFT_INTAKE"
    INFO_REQUIRED = "INFO_REQUIRED"
    RFI_SEARCHING = "RFI_SEARCHING"
    RFI_MATCH_OFFERED = "RFI_MATCH_OFFERED"
    RFI_NO_MATCH = "RFI_NO_MATCH"
    JIOC_REVIEW = "JIOC_REVIEW"
    COLLECT_CHOICE = "COLLECT_CHOICE"
    ANALYST_ASSIGNMENT = "ANALYST_ASSIGNMENT"
    ANALYST_IN_PROGRESS = "ANALYST_IN_PROGRESS"
    MANAGER_APPROVAL = "MANAGER_APPROVAL"
    QC_REVIEW = "QC_REVIEW"
    REWORK_REQUIRED = "REWORK_REQUIRED"
    DISSEMINATION_READY = "DISSEMINATION_READY"
    CLOSED_DELIVERED = "CLOSED_DELIVERED"
    CLOSED_EXISTING_PRODUCT_ACCEPTED = "CLOSED_EXISTING_PRODUCT_ACCEPTED"
    CANCELLED = "CANCELLED"

    @classmethod
    def _missing_(cls, value: object) -> "TicketState | None":
        # States retired by the JIOC restructure still decode from persisted
        # tickets; the codec reconstructs enums by value.
        return _LEGACY_TICKET_STATES.get(value) if isinstance(value, str) else None


_LEGACY_TICKET_STATES: dict[str, TicketState] = {
    "ROUTE_ASSESSMENT": TicketState.JIOC_REVIEW,
    "RFA_MANAGER_REVIEW": TicketState.JIOC_REVIEW,
    "CM_MANAGER_REVIEW": TicketState.JIOC_REVIEW,
    # QC now owns the final release; tickets awaiting the retired manager
    # release step return to QC for a benign re-approval.
    "MANAGER_RELEASE": TicketState.QC_REVIEW,
}
