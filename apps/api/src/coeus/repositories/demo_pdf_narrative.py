"""Scenario-aware narrative text for deterministic synthetic intelligence PDFs."""

from coeus.domain.store import StoreProduct


def judgements(product: StoreProduct) -> tuple[str, ...]:
    metadata = product.metadata
    primary, secondary, tertiary = _themes(product)
    return (
        f"Within this fictional exercise, {primary} activity around "
        f"{metadata.area_or_region} increased during the stated reporting window.",
        f"Invented records place {secondary} and {tertiary} indicators in the same mock "
        "timeline, but do not establish cause or intent.",
        "Training, maintenance and reporting artefacts remain equally plausible alternative "
        "explanations; no unit identity or precise location is represented.",
        "Any follow-on exercise tasking should preserve the ACG boundary, cite the coverage "
        "period and restate the mock-data caveat.",
    )


def indicator_observation(product: StoreProduct, theme: str, index: int) -> str:
    metadata = product.metadata
    themes = _themes(product)
    related = next(value for value in themes if value != theme.casefold())
    complementary = next(
        value for value in reversed(themes) if value not in {theme.casefold(), related}
    )
    region = metadata.area_or_region.replace(" (synthetic)", "")[:34]
    observations = (
        f"Invented logs show increased {theme.casefold()} activity in the {region} exercise.",
        f"A mock warning feed pairs {theme.casefold()} with {related}; no event is real.",
        f"Synthetic readiness records connect {theme.casefold()} and {complementary} on two days.",
        f"Fictional reporting shows {theme.casefold()} rising inside the stated time window.",
        f"A simulated review records uneven {theme.casefold()} availability and coordination.",
        f"Mock after-action notes request more collection on {theme.casefold()} indicators.",
    )
    return observations[index]


def assessment_sections(product: StoreProduct) -> tuple[tuple[str, str], ...]:
    metadata = product.metadata
    primary, secondary, tertiary = _themes(product)
    period = f"{metadata.time_period_start} to {metadata.time_period_end}"
    return (
        (
            "Assessment",
            f"Across {metadata.area_or_region}, fabricated reporting for {period} suggests a "
            f"notional relationship between {primary}, {secondary} and {tertiary}. The pattern "
            "exists only to exercise search, comparison and analytic review.",
        ),
        (
            "Implications",
            "A synthetic customer could use the report to frame questions about warning, force "
            "protection, logistics and decision timing. It provides no basis for real-world "
            "planning or targeting.",
        ),
        (
            "Collection gaps",
            "The exercise record intentionally omits verified unit identity, coordinates, "
            "technical parameters, source provenance and corroboration. Those gaps must remain "
            "visible in any mock workflow response.",
        ),
        (
            "Methodology",
            "Coeus generated this document deterministically from synthetic specifications. "
            "Search metadata mirrors its themes. No external source, network service or "
            "generative model contributed content.",
        ),
    )


def _themes(product: StoreProduct) -> tuple[str, str, str]:
    ignored = {
        "mock-data",
        "synthetic-exercise",
        "synthetic-conflict",
        "russia",
        "ukraine",
    }
    values = list(
        dict.fromkeys(tag.replace("-", " ") for tag in sorted(product.metadata.tags - ignored))
    )
    values.extend(value for value in ("activity", "readiness", "warning") if value not in values)
    return values[0], values[1], values[2]
