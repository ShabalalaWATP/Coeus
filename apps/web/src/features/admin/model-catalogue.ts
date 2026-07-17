export type ModelInfo = {
  tier: string;
  description: string;
};

const MODEL_CATALOGUE: Record<string, ModelInfo> = {
  "gemini-3.1-pro-preview": {
    tier: "Advanced",
    description: "Google's preview Pro model for complex reasoning and agentic workflows.",
  },
  "gemini-3.5-flash": {
    tier: "Advanced",
    description:
      "Google's current stable Flash model for agentic, coding and long-horizon workflows.",
  },
  "gemma-4-31b-it": {
    tier: "Open",
    description: "Google's largest hosted Gemma 4 instruction-tuned model.",
  },
  "gemma-4-26b-a4b-it": {
    tier: "Open",
    description: "Google's hosted Gemma 4 mixture-of-experts instruction model.",
  },
  "gpt-5.6-sol": {
    tier: "Advanced",
    description: "OpenAI's flagship model for complex professional work and advanced reasoning.",
  },
  "gpt-5.6-terra": {
    tier: "Balanced",
    description: "OpenAI's balanced model for strong intelligence, latency and cost.",
  },
  "gpt-5.6-luna": {
    tier: "Fast",
    description: "OpenAI's cost-efficient model for high-volume and latency-sensitive workloads.",
  },
  "gpt-realtime-mini": {
    tier: "Voice",
    description: "OpenAI's low-latency speech-to-speech model for live voice drafting.",
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
