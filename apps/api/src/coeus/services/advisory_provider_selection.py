"""Frozen provider selection with per-agent hosted egress approval."""

from dataclasses import dataclass
from hashlib import sha256

from coeus.core.config import Settings
from coeus.core.deployment import HOSTED_ENVIRONMENTS
from coeus.domain.advisory_agents import AdvisoryAgentKind, AdvisoryPrompt
from coeus.integrations.llm_gateway import LlmCall
from coeus.services.ai_models import AiModelService
from coeus.services.ai_provider_catalog import initial_api_keys, spec_for


@dataclass(frozen=True)
class AdvisoryProviderSelection:
    provider: str
    model: str
    input_hash: str
    call: LlmCall | None
    unavailable_outcome: str | None = None
    error_class: str | None = None


def freeze_advisory_provider(
    settings: Settings,
    ai_models: AiModelService | None,
    agent: AdvisoryAgentKind,
    prompt: AdvisoryPrompt,
) -> AdvisoryProviderSelection:
    if ai_models is not None:
        provider = ai_models.provider()
        api_key = ai_models.api_key(provider)
        model = ai_models.active_model(provider)
    else:
        provider = settings.llm_provider
        api_key = initial_api_keys(settings).get(provider)
        spec = spec_for(settings, provider)
        model = spec.default_model if spec else ""
    input_hash = _prompt_hash(prompt)
    if provider == "mock" or not api_key:
        return AdvisoryProviderSelection(provider, model, input_hash, None)
    if not _remote_egress_approved(settings, agent, provider):
        return AdvisoryProviderSelection(
            provider,
            model,
            input_hash,
            None,
            "remote_egress_not_approved_fallback",
            "AgentRemoteEgressNotApproved",
        )
    call = LlmCall(
        provider=provider,
        model=model,
        api_key=api_key,
        prompt=prompt.data,
        timeout=settings.llm_api_timeout_seconds,
        region=settings.bedrock_region,
        instructions=prompt.instructions,
        max_output_tokens=prompt.max_output_tokens,
        structured_output=True,
        litellm_base_url=settings.litellm_base_url,
        hosted=settings.environment in HOSTED_ENVIRONMENTS,
    )
    return AdvisoryProviderSelection(provider, model, input_hash, call)


def _remote_egress_approved(settings: Settings, agent: AdvisoryAgentKind, provider: str) -> bool:
    if settings.environment not in HOSTED_ENVIRONMENTS:
        return True
    enabled = {
        AdvisoryAgentKind.INTAKE_PLANNER: False,
        AdvisoryAgentKind.SEARCH_PLANNER: settings.search_planner_remote_enabled,
        AdvisoryAgentKind.ROUTING_CRITIC: settings.routing_critic_remote_enabled,
    }[agent]
    return (
        enabled
        and provider in settings.advisory_approved_providers
        and "synthetic" in settings.advisory_approved_data_classifications
    )


def _prompt_hash(prompt: AdvisoryPrompt) -> str:
    value = f"{prompt.instructions}\n{prompt.data}"
    return f"sha256:{sha256(value.encode('utf-8')).hexdigest()}"
