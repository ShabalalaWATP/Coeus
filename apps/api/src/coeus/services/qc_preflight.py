"""Deterministic QC-agent preflight before mandatory human release review."""

from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from coeus.core.errors import AppError
from coeus.domain.auth import UserAccount
from coeus.domain.qc import QcAgentCheck, QcAgentPreflight, QcAgentPreflightStatus
from coeus.domain.tickets import AgentRun, AgentRunStatus, DraftProductVersion, TicketRecord
from coeus.services.qc_proofing import proofing_findings
from coeus.services.ticket_records import timeline
from coeus.services.tickets import TicketServices

POLICY_VERSION = "qc-preflight-v1"
AGENT_NAME = "qc-preflight-agent"


class QcPreflightAgent:
    """Records reproducible structural checks and abstains on any blocker.

    The preflight never releases a product. Its result is an additional gate
    before, not a replacement for, the human QC checklist and release decision.
    """

    def __init__(self, tickets: TicketServices) -> None:
        self._tickets = tickets

    def ensure_current(
        self, actor: UserAccount, ticket: TicketRecord
    ) -> tuple[TicketRecord, QcAgentPreflight]:
        draft = _latest_draft(ticket)
        input_hash = _input_hash(ticket, draft)
        current = next(
            (
                item
                for item in reversed(ticket.qc_agent_preflights)
                if item.draft_version_id == draft.version_id and item.input_hash == input_hash
            ),
            None,
        )
        if current is not None:
            return ticket, current

        preflight = _evaluate(ticket, draft, input_hash)
        run = AgentRun(
            run_id=uuid4(),
            ticket_id=ticket.ticket_id,
            agent_name=AGENT_NAME,
            status=AgentRunStatus.COMPLETED,
            summary=(
                "QC preflight passed; human QC remains mandatory."
                if preflight.status == QcAgentPreflightStatus.PASSED
                else "QC preflight blocked release pending human-led rework."
            ),
            safety_flags=preflight.blockers,
            created_at=preflight.created_at,
        )
        proposed = replace(
            ticket,
            qc_agent_preflights=(*ticket.qc_agent_preflights, preflight),
            agent_runs=(*ticket.agent_runs, run),
            timeline=(
                *ticket.timeline,
                timeline(
                    ticket.ticket_id,
                    actor.user_id,
                    "qc_agent_preflight_completed",
                    "Automated preflight completed; a human QC decision is still required.",
                ),
            ),
        )
        updated = self._tickets.mutations.save_audited_if_current(
            ticket,
            proposed,
            "qc_agent_preflight_completed",
            actor,
            {
                "ticket_id": str(ticket.ticket_id),
                "status": preflight.status.value,
                "policy_version": POLICY_VERSION,
            },
        )
        return updated, preflight

    def require_passed(self, actor: UserAccount, ticket: TicketRecord) -> TicketRecord:
        updated, preflight = self.ensure_current(actor, ticket)
        if preflight.status != QcAgentPreflightStatus.PASSED:
            raise AppError(
                409,
                "qc_agent_preflight_failed",
                "Automated preflight found blockers. Return the product for rework.",
            )
        return updated


def _latest_draft(ticket: TicketRecord) -> DraftProductVersion:
    if not ticket.draft_products:
        raise AppError(409, "draft_required", "A draft product is required for QC preflight.")
    return ticket.draft_products[-1]


def _evaluate(
    ticket: TicketRecord, draft: DraftProductVersion, input_hash: str
) -> QcAgentPreflight:
    marker_ready = "mock data only" in f"{draft.summary} {draft.content}".casefold()
    checks = (
        _check(
            "requirement_present",
            bool(ticket.intake.operational_question),
            "Question captured.",
        ),
        _check(
            "draft_complete",
            all((draft.title.strip(), draft.summary.strip(), draft.content.strip())),
            "Title, summary and content are present.",
        ),
        _check(
            "evidence_review_ready",
            bool(ticket.linked_products) or len(draft.content.strip()) >= 20,
            "Draft contains a reviewable evidence narrative.",
        ),
        _check("assets_valid", _assets_valid(draft), "Attached asset metadata is well formed."),
        _check(
            "synthetic_data_marker",
            marker_ready,
            "Repository-safe synthetic data marking is present.",
        ),
        _check(
            "human_release_controls_pending",
            True,
            "Classification, sources, access and releasability require human confirmation.",
        ),
        _check(
            "manager_approved_version",
            not draft.manifest_hash or ticket.manager_approved_manifest_hash == draft.manifest_hash,
            "Manager approval matches the immutable product manifest.",
        ),
    )
    blockers = tuple(item.key for item in checks if not item.passed)
    return QcAgentPreflight(
        preflight_id=uuid4(),
        ticket_id=ticket.ticket_id,
        draft_version_id=draft.version_id,
        input_hash=input_hash,
        status=(QcAgentPreflightStatus.BLOCKED if blockers else QcAgentPreflightStatus.PASSED),
        checks=checks,
        blockers=blockers,
        policy_version=POLICY_VERSION,
        created_at=datetime.now(UTC),
        findings=proofing_findings(draft),
    )


def _check(key: str, passed: bool, detail: str) -> QcAgentCheck:
    return QcAgentCheck(key=key, passed=passed, detail=detail)


def _assets_valid(draft: DraftProductVersion) -> bool:
    return bool(draft.assets) and all(
        asset.name.strip() and asset.size_bytes > 0 and len(asset.sha256) == 64
        for asset in draft.assets
    )


def _input_hash(ticket: TicketRecord, draft: DraftProductVersion) -> str:
    values = (
        ticket.intake.operational_question or "",
        ticket.intake.customer_success_criteria or "",
        str(draft.version_id),
        draft.title,
        draft.summary,
        draft.content,
        *(f"{asset.name}|{asset.size_bytes}|{asset.sha256}" for asset in draft.assets),
        *(str(item.product_id) for item in ticket.linked_products),
    )
    return sha256("\u241f".join(values).encode("utf-8")).hexdigest()
