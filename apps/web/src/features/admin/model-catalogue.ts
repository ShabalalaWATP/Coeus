export type ModelInfo = {
  tier: string;
  description: string;
};

const MODEL_CATALOGUE: Record<string, ModelInfo> = {
  "gemma-4-31b": {
    tier: "Sovereign",
    description:
      "Self-hosted Gemma weights for air-gapped or data-sovereignty constrained deployments.",
  },
  "gemini-2.5-flash": {
    tier: "Fast",
    description: "Low-latency intake extraction and RFI search at the lowest cost per request.",
  },
  "gemini-2.5-pro": {
    tier: "Advanced",
    description: "Deeper reasoning for capability assessments and complex tasking summaries.",
  },
  "gemini-3-flash": {
    tier: "Fast",
    description: "Latest flash generation with stronger tool use at near-flash latency.",
  },
  "gpt-5": {
    tier: "Advanced",
    description: "OpenAI's flagship reasoning model for complex assessment support.",
  },
  "gpt-5-mini": {
    tier: "Fast",
    description: "Low-latency OpenAI model suited to conversational intake.",
  },
  "gpt-4.1": {
    tier: "Advanced",
    description: "Previous-generation OpenAI model kept for continuity of behaviour.",
  },
  "anthropic.claude-sonnet-4-5-20250929-v1:0": {
    tier: "Advanced",
    description: "Claude Sonnet 4.5 on Bedrock for deeper reasoning within AWS.",
  },
  "anthropic.claude-haiku-4-5-20251001-v1:0": {
    tier: "Fast",
    description: "Claude Haiku 4.5 on Bedrock for low-latency intake replies.",
  },
};

const FALLBACK_MODEL_INFO: ModelInfo = {
  tier: "Custom",
  description: "Deployment-specific model registered by your platform administrator.",
};

export function modelInfoFor(model: string): ModelInfo {
  return MODEL_CATALOGUE[model] ?? FALLBACK_MODEL_INFO;
}
