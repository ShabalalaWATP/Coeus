from re import findall

from coeus.domain.store import StoreProduct

SEMANTIC_LABEL_TERMS: dict[str, frozenset[str]] = {
    "assessment": frozenset({"assessment", "assess", "brief", "report", "analysis"}),
    "collection": frozenset({"collection", "collect", "tasking", "source"}),
    "maritime": frozenset(
        {"maritime", "port", "ports", "harbour", "vessel", "vessels", "shipping"}
    ),
    "geospatial": frozenset({"geospatial", "geojson", "map", "imagery", "terrain"}),
    "cyber": frozenset({"cyber", "malware", "intrusion", "network", "credential"}),
    "sigint": frozenset({"sigint", "signals", "emitter", "radar", "sensor"}),
    "humint": frozenset({"humint", "human", "liaison", "source", "intent"}),
    "osint": frozenset({"osint", "media", "public", "social", "open"}),
    "finance": frozenset({"finance", "financial", "sanctions", "payment", "ownership"}),
    "infrastructure": frozenset({"infrastructure", "energy", "power", "rail", "pipeline"}),
    "aviation": frozenset({"air", "aviation", "runway", "aircraft", "flight"}),
    "space": frozenset({"space", "satellite", "orbital", "launch"}),
    "health": frozenset({"health", "medical", "disease", "hospital"}),
    "supply-chain": frozenset({"supply", "logistics", "freight", "cargo"}),
    "border": frozenset({"border", "crossing", "checkpoint", "migration"}),
    "environment": frozenset({"weather", "climate", "flood", "wildfire"}),
}


def derive_semantic_labels(*parts: str, existing: frozenset[str] | None = None) -> frozenset[str]:
    tokens = _tokens(" ".join(parts))
    labels = set(existing or ())
    for label, terms in SEMANTIC_LABEL_TERMS.items():
        if tokens.intersection(terms):
            labels.add(label)
    if not labels:
        labels.add("general-intelligence")
    return frozenset(sorted(labels))


def product_semantic_text(product: StoreProduct) -> str:
    metadata = product.metadata
    return " ".join(
        (
            metadata.title,
            metadata.summary,
            metadata.description,
            metadata.product_type,
            metadata.source_type,
            metadata.owner_team,
            metadata.area_or_region,
            " ".join(metadata.tags),
            " ".join(effective_semantic_labels(product)),
            " ".join(asset.asset_type for asset in product.assets),
        )
    )


def effective_semantic_labels(product: StoreProduct) -> frozenset[str]:
    metadata = product.metadata
    return derive_semantic_labels(
        metadata.title,
        metadata.summary,
        metadata.description,
        metadata.product_type,
        metadata.source_type,
        metadata.owner_team,
        metadata.area_or_region,
        " ".join(metadata.tags),
        " ".join(asset.asset_type for asset in product.assets),
        existing=metadata.semantic_labels,
    )


def semantic_label_reasons(product: StoreProduct, query_text: str) -> tuple[str, ...]:
    query_labels = derive_semantic_labels(query_text)
    matches = query_labels.intersection(effective_semantic_labels(product))
    return tuple(f"semantic-label:{label}" for label in sorted(matches))


def _tokens(value: str) -> frozenset[str]:
    return frozenset(findall(r"[a-z0-9-]+", value.casefold()))
