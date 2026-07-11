import { screen } from "@testing-library/react";

export const providers = [
  {
    name: "gemini_api",
    label: "Gemini API (primary)",
    models: ["gemma-4-31b", "gemini-2.5-flash", "gemini-2.5-pro"],
    activeModel: "gemma-4-31b",
    apiKeyConfigured: false,
    supportsModelRefresh: true,
  },
  {
    name: "openai_api",
    label: "OpenAI API",
    models: ["gpt-5", "gpt-5-mini"],
    activeModel: "gpt-5-mini",
    apiKeyConfigured: false,
    supportsModelRefresh: true,
  },
  {
    name: "vertex_ai",
    label: "GCP Vertex AI",
    models: ["gemini-2.5-flash"],
    activeModel: "gemini-2.5-flash",
    apiKeyConfigured: false,
    supportsModelRefresh: false,
  },
  {
    name: "mock",
    label: "Mock (offline)",
    models: ["mock"],
    activeModel: "mock",
    apiKeyConfigured: false,
    supportsModelRefresh: false,
  },
];

export const modelState = {
  provider: "gemini_api",
  activeModel: "gemma-4-31b",
  availableModels: ["gemma-4-31b", "gemini-2.5-flash", "gemini-2.5-pro"],
  apiKeyConfigured: false,
  embeddingProvider: "mock",
  embeddedProductCount: 3,
  changedBy: null,
  changedAt: null,
  providers,
};

export const liveRegion = () => screen.getByRole("group", { name: "Live AI configuration" });
