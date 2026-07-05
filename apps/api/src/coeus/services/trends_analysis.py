from dataclasses import dataclass
from uuid import UUID

from coeus.domain.tickets import TicketRecord


@dataclass(frozen=True)
class ProductReuseMetric:
    product_id: UUID
    reference: str
    title: str
    owner_team: str
    dissemination_count: int
    accepted_offer_count: int
    feedback_count: int
    average_rating: float | None


@dataclass(frozen=True)
class TrendInsight:
    title: str
    summary: str
    signal: str
    confidence: float


class TrendsAnalysisAgent:
    def analyse(
        self,
        tickets: tuple[TicketRecord, ...],
        reuse: tuple[ProductReuseMetric, ...],
        average_rating: float | None,
    ) -> tuple[TrendInsight, ...]:
        if not tickets:
            return (
                TrendInsight(
                    title="No trend baseline yet",
                    summary="No eligible tickets exist for this analytics scope.",
                    signal="neutral",
                    confidence=0.6,
                ),
            )
        return (
            self._region_trend(tickets),
            self._reuse_trend(reuse),
            self._feedback_trend(average_rating),
        )

    @staticmethod
    def _region_trend(tickets: tuple[TicketRecord, ...]) -> TrendInsight:
        regions: dict[str, int] = {}
        for ticket in tickets:
            region = ticket.intake.area_or_region or "Unspecified"
            regions[region] = regions.get(region, 0) + 1
        region, count = max(regions.items(), key=lambda item: (item[1], item[0]))
        return TrendInsight(
            title="Dominant request region",
            summary=f"{region} is the leading request area with {count} ticket(s).",
            signal="watch",
            confidence=0.74,
        )

    @staticmethod
    def _reuse_trend(reuse: tuple[ProductReuseMetric, ...]) -> TrendInsight:
        if not reuse:
            return TrendInsight(
                title="Product reuse not established",
                summary="No disseminated or accepted product reuse has been recorded yet.",
                signal="neutral",
                confidence=0.65,
            )
        top = max(
            reuse,
            key=lambda item: (
                item.dissemination_count + item.accepted_offer_count,
                item.feedback_count,
                item.title,
            ),
        )
        total = top.dissemination_count + top.accepted_offer_count
        return TrendInsight(
            title="Reusable product signal",
            summary=f"{top.title} leads reuse with {total} dissemination or acceptance event(s).",
            signal="positive",
            confidence=0.78,
        )

    @staticmethod
    def _feedback_trend(average_rating: float | None) -> TrendInsight:
        if average_rating is None:
            return TrendInsight(
                title="Feedback pending",
                summary="Feedback requests exist but no requester ratings are submitted yet.",
                signal="neutral",
                confidence=0.7,
            )
        signal = "positive" if average_rating >= 4 else "watch"
        return TrendInsight(
            title="Requester satisfaction",
            summary=f"Submitted feedback averages {average_rating:.1f} out of 5.",
            signal=signal,
            confidence=0.82,
        )
