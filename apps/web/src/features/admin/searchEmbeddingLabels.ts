export const searchProviderLabels: Record<string, string> = {
  gemini_api: "Gemini API",
  mock: "Local search",
};

export const searchModelLabels: Record<string, string> = {
  "gemini-embedding-2": "Gemini Embedding 2",
  "gemini-embedding-001": "Gemini Embedding 001",
  "token-hash-v2": "Local Search v2",
};

export function searchProviderLabel(provider: string) {
  return searchProviderLabels[provider] ?? provider;
}

export function searchModelLabel(model: string) {
  return searchModelLabels[model] ?? model;
}
