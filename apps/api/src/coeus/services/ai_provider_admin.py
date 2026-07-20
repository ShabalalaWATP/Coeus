"""Admin helpers for LLM provider management.

Connection tests let an administrator prove a key works before activating a
provider, and the change notification makes the app-wide consequence of a
switch visible to every administrator, not just the one who clicked.
"""

from dataclasses import dataclass

from coeus.core.advisory_egress import HOSTED_ENVIRONMENTS
from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import UserAccount
from coeus.integrations.llm_gateway import LlmCall, generate_text
from coeus.services.ai_models import AiModelService
from coeus.services.ai_provider_catalog import spec_for
from coeus.services.notifications import NotificationService

TEST_PROMPT = "Connection check: reply with the single word OK."


@dataclass(frozen=True)
class ConnectionTestResult:
    ok: bool
    provider: str
    model: str
    message: str


def test_connection(
    settings: Settings, ai_models: AiModelService, provider: str | None
) -> ConnectionTestResult:
    """Send one tiny prompt through a provider and report the outcome.

    Never raises for reachability problems: the result is a report the admin
    reads, not an error path. Unknown provider names are still rejected.
    """
    name = provider or ai_models.provider()
    spec = spec_for(settings, name)
    if spec is None:
        raise AppError(422, "provider_not_available", "The requested provider is not available.")
    model = ai_models.active_model(spec.name)
    if spec.name == "mock":
        return ConnectionTestResult(
            ok=True,
            provider=spec.name,
            model=model,
            message="The mock provider replies locally; no external call was made.",
        )
    api_key = ai_models.api_key(spec.name)
    if not api_key:
        return ConnectionTestResult(
            ok=False,
            provider=spec.name,
            model=model,
            message="No API key is configured for this provider.",
        )
    call = LlmCall(
        provider=spec.name,
        model=model,
        api_key=api_key,
        prompt=TEST_PROMPT,
        timeout=settings.llm_api_timeout_seconds,
        region=settings.bedrock_region,
        litellm_base_url=settings.litellm_base_url,
        hosted=settings.environment in HOSTED_ENVIRONMENTS,
    )
    try:
        text = generate_text(call)
    except AppError as error:
        return ConnectionTestResult(
            ok=False, provider=spec.name, model=model, message=error.message
        )
    if not text:
        return ConnectionTestResult(
            ok=False,
            provider=spec.name,
            model=model,
            message="The provider answered but returned no usable text.",
        )
    return ConnectionTestResult(
        ok=True, provider=spec.name, model=model, message=f"{model} answered the test prompt."
    )


def notify_admins_of_provider_change(
    notifications: NotificationService,
    users: tuple[UserAccount, ...],
    actor: UserAccount,
    settings: Settings,
    provider: str,
    model: str,
) -> None:
    """Tell every administrator the live AI provider changed for all users."""
    spec = spec_for(settings, provider)
    label = spec.label if spec is not None else provider
    for user in users:
        if not user.is_active or Permission.SYSTEM_CONFIGURE not in user.permissions:
            continue
        notifications.notify(
            user,
            "ai_provider_changed",
            "AI provider changed",
            f"{actor.username} activated {label} ({model}) as the live AI provider. "
            "This applies to every user of the application immediately.",
            link_path="/admin",
        )
