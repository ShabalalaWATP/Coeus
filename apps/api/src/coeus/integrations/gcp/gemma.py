from dataclasses import dataclass

from coeus.core.config import Settings


@dataclass(frozen=True)
class GemmaVertexConfig:
    project_id: str
    location: str
    model: str


def gemma_vertex_config_from_settings(settings: Settings) -> GemmaVertexConfig | None:
    if settings.llm_provider != "gemma_vertex":
        return None
    project_id = settings.gemma_vertex_project_id or settings.gcp_project_id
    if not project_id:
        raise ValueError("Gemma Vertex provider requires COEUS_GCP_PROJECT_ID.")
    return GemmaVertexConfig(
        project_id=project_id,
        location=settings.gemma_vertex_location,
        model=settings.gemma_vertex_model,
    )
