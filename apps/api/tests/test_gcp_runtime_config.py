import pytest

from coeus.core.config import Settings
from coeus.integrations.gcp.gemma import gemma_vertex_config_from_settings


def test_gemma_vertex_config_uses_gcp_project_fallback() -> None:
    config = gemma_vertex_config_from_settings(
        Settings(
            llm_provider="gemma_vertex",
            gcp_project_id="coeus-501415",
            gemma_vertex_location="europe-west2",
            gemma_vertex_model="gemma-test",
        )
    )

    assert config is not None
    assert config.project_id == "coeus-501415"
    assert config.location == "europe-west2"
    assert config.model == "gemma-test"


def test_gemma_vertex_config_can_override_project() -> None:
    config = gemma_vertex_config_from_settings(
        Settings(
            llm_provider="gemma_vertex",
            gcp_project_id="coeus-501415",
            gemma_vertex_project_id="coeus-models",
        )
    )

    assert config is not None
    assert config.project_id == "coeus-models"


def test_gemma_vertex_config_is_absent_for_mock_provider() -> None:
    assert gemma_vertex_config_from_settings(Settings(llm_provider="mock")) is None


def test_gemma_vertex_config_requires_project_id() -> None:
    with pytest.raises(ValueError, match="COEUS_GCP_PROJECT_ID"):
        gemma_vertex_config_from_settings(Settings(llm_provider="gemma_vertex"))


def test_dev_runtime_requires_seed_user_opt_in_and_secrets() -> None:
    settings = Settings(environment="dev", secure_cookies=True)

    with pytest.raises(ValueError, match="Seed users"):
        settings.require_runtime_security()


def test_dev_runtime_allows_explicit_seed_user_opt_in() -> None:
    settings = Settings(
        environment="dev",
        allow_dev_seed_users=True,
        secure_cookies=True,
        session_secret="s" * 32,
        csrf_secret="c" * 32,
    )

    settings.require_runtime_security()
