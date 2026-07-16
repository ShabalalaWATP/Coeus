import { screen } from "@testing-library/react";

export const providers = [
  {
    name: "gemini_api",
    label: "Gemini API (primary)",
    models: ["gemini-3.5-flash", "gemini-3.1-pro-preview", "gemma-4-31b-it", "gemma-4-26b-a4b-it"],
    activeModel: "gemma-4-31b-it",
    apiKeyConfigured: false,
    supportsModelRefresh: false,
  },
  {
    name: "openai_api",
    label: "OpenAI API",
    models: ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"],
    activeModel: "gpt-5.6-terra",
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
  activeModel: "gemma-4-31b-it",
  availableModels: [
    "gemini-3.5-flash",
    "gemini-3.1-pro-preview",
    "gemma-4-31b-it",
    "gemma-4-26b-a4b-it",
  ],
  apiKeyConfigured: false,
  embeddingProvider: "mock",
  embeddedProductCount: 3,
  changedBy: null,
  changedAt: null,
  providers,
};

export const liveRegion = () => screen.getByRole("group", { name: "Live AI configuration" });
