from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ROUTES = REPOSITORY_ROOT / "infra" / "litellm" / "model-routes.example.yaml"
PROVIDER_ENV = REPOSITORY_ROOT / "infra" / "litellm" / "provider.env.example"


def test_litellm_cloud_routes_use_stable_aliases_and_environment_inputs() -> None:
    routes = ROUTES.read_text(encoding="utf-8")

    assert "model_name: istari-bedrock-primary" in routes
    assert "model: os.environ/LITELLM_BEDROCK_MODEL" in routes
    assert "aws_region_name: os.environ/AWS_REGION_NAME" in routes
    assert "model_name: istari-vertex-primary" in routes
    assert "model: os.environ/LITELLM_VERTEX_MODEL" in routes
    assert "vertex_project: os.environ/VERTEXAI_PROJECT" in routes
    assert "vertex_location: os.environ/VERTEXAI_LOCATION" in routes
    assert "drop_params: false" in routes
    assert "turn_off_message_logging: true" in routes


def test_litellm_examples_do_not_contain_cloud_or_proxy_credentials() -> None:
    examples = "\n".join(
        (
            ROUTES.read_text(encoding="utf-8"),
            PROVIDER_ENV.read_text(encoding="utf-8"),
        )
    )
    forbidden = (
        "AWS_ACCESS_KEY_ID=",
        "AWS_SECRET_ACCESS_KEY=",
        "AWS_SESSION_TOKEN=",
        "GOOGLE_APPLICATION_CREDENTIALS=",
        "private_key",
        "LITELLM_MASTER_KEY=",
        "COEUS_LITELLM_API_KEY=",
    )

    assert all(value not in examples for value in forbidden)
    assert "bedrock/*" not in examples
    assert "vertex_ai/*" not in examples
