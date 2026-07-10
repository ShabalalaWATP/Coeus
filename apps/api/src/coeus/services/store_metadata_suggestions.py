from coeus.domain.store import MetadataSuggestion
from coeus.services.store_semantics import derive_semantic_labels


class MetadataSuggestionService:
    def suggest(
        self, title: str, summary: str, product_type: str, area_or_region: str
    ) -> MetadataSuggestion:
        text = f"{title} {summary} {product_type} {area_or_region}".casefold()
        tags = []
        if "baltic" in text:
            tags.append("baltic")
        if product_type == "geographic_product":
            tags.append("geographic")
        tags.append("mock")
        entities = (area_or_region, "MOCK DATA ONLY")
        labels = derive_semantic_labels(title, summary, product_type, area_or_region)
        return MetadataSuggestion(
            tags=tuple(dict.fromkeys(tags)),
            entities=entities,
            source_type="synthetic",
            acg_ids=(),
            semantic_labels=tuple(labels),
        )
