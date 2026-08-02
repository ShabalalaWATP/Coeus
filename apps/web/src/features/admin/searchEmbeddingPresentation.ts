import type { SearchEmbeddingState } from "../../lib/api-client/admin";

export type SearchPresentation = {
  description: string;
  isUpdating: boolean;
  needsAttention: boolean;
  statusLabel: string;
  statusTone: "active" | "attention" | "neutral";
  title: string;
};

export function searchEmbeddingPresentation(state: SearchEmbeddingState): SearchPresentation {
  const service = state.provider === "gemini_api" ? "Gemini search" : "Local search";
  const products = new Intl.NumberFormat("en-GB").format(state.productCount);

  if (state.indexStatus === "stale" || state.indexStatus === "indexing") {
    return {
      description:
        "Istari noticed a change and is updating the search library automatically. You can leave this page.",
      isUpdating: true,
      needsAttention: false,
      statusLabel: "Updating automatically",
      statusTone: "neutral",
      title: state.provider === "gemini_api" ? "Preparing Gemini search" : "Preparing local search",
    };
  }

  if (state.indexStatus === "failed" || state.indexStatus === "degraded") {
    return {
      description:
        "Istari could not finish the automatic update. Search may be limited until it is tried again.",
      isUpdating: false,
      needsAttention: true,
      statusLabel: "Needs attention",
      statusTone: "attention",
      title: "Search needs attention",
    };
  }

  return {
    description: `${service} is ready to search ${products} intelligence products.`,
    isUpdating: false,
    needsAttention: false,
    statusLabel: "Ready",
    statusTone: "active",
    title: `${service} is ready`,
  };
}

export function searchFailureMessage(reason: string | null) {
  const messages: Record<string, string> = {
    invalid_api_key: "The saved Gemini key was rejected.",
    provider_unavailable: "The configured search service could not be reached.",
    rate_limited: "The search service is temporarily busy.",
  };
  return reason
    ? (messages[reason] ?? "The latest search library update did not finish.")
    : "The latest search library update did not finish.";
}
