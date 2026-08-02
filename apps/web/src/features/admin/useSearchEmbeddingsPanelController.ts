import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  configureSearchEmbeddingKey,
  configureSearchEmbeddings,
  getSearchEmbeddingState,
  reindexSearchEmbeddings,
  testSearchEmbeddings,
  type SearchEmbeddingState,
} from "../../lib/api-client/admin";

const QUERY_KEY = ["admin-search-embeddings"] as const;
const SEARCH_MODELS: Record<string, string[]> = {
  gemini_api: ["gemini-embedding-2", "gemini-embedding-001"],
  mock: ["token-hash-v2"],
};

export function useSearchEmbeddingsPanelController(csrfToken: string) {
  const queryClient = useQueryClient();
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [egressConfirmed, setEgressConfirmedState] = useState(false);
  const [testedConfiguration, setTestedConfiguration] = useState<string | null>(null);
  const query = useQuery({
    queryKey: QUERY_KEY,
    queryFn: getSearchEmbeddingState,
    refetchInterval: (current) => searchStatusRefreshInterval(current.state.data?.indexStatus),
  });
  const state = query.data;
  const provider = selectedProvider ?? state?.provider ?? "mock";
  const models =
    SEARCH_MODELS[provider] ?? (provider === state?.provider ? state.availableModels : []);
  const model = selectedModel ?? (provider === state?.provider ? state.model : (models[0] ?? ""));
  const draftKey = configurationKey(provider, model);
  const updateCache = (next: SearchEmbeddingState) => queryClient.setQueryData(QUERY_KEY, next);
  const clearTest = () => {
    setTestedConfiguration(null);
    testMutation.reset();
  };
  const keyMutation = useMutation({
    mutationFn: () => configureSearchEmbeddingKey(apiKey.trim(), csrfToken),
    onMutate: clearTest,
    onSuccess: (next) => {
      setApiKey("");
      updateCache(next);
    },
  });
  const testMutation = useMutation({
    mutationFn: () => testSearchEmbeddings(provider, model, egressConfirmed, csrfToken),
    onMutate: () => setTestedConfiguration(null),
    onSuccess: (result) => {
      setTestedConfiguration(result.ok ? configurationKey(result.provider, result.model) : null);
    },
  });
  const configurationMutation = useMutation({
    mutationFn: () => configureSearchEmbeddings(provider, model, egressConfirmed, csrfToken),
    onSuccess: (next) => {
      setSelectedProvider(next.provider);
      setSelectedModel(next.model);
      updateCache(next);
    },
  });
  const reindexMutation = useMutation({
    mutationFn: () => reindexSearchEmbeddings(csrfToken),
    onSuccess: updateCache,
  });
  const selectProvider = (next: string) => {
    setSelectedProvider(next);
    setSelectedModel(SEARCH_MODELS[next]?.[0] ?? "");
    setEgressConfirmedState(false);
    clearTest();
  };
  const selectModel = (next: string) => {
    setSelectedModel(next);
    clearTest();
  };
  const updateApiKey = (next: string) => {
    setApiKey(next);
    clearTest();
  };
  const setEgressConfirmed = (next: boolean) => {
    setEgressConfirmedState(next);
    clearTest();
  };
  const actionPending = [keyMutation, testMutation, configurationMutation, reindexMutation].some(
    (mutation) => mutation.isPending,
  );
  const providerReady = provider === "mock" || Boolean(state?.apiKeyConfigured);
  const egressReady = provider !== "gemini_api" || egressConfirmed;
  const configurationChanged =
    Boolean(state) && (provider !== state?.provider || model !== state.model);

  return {
    query,
    state,
    provider,
    model,
    models,
    apiKey,
    egressConfirmed,
    testedConfiguration,
    draftTested: testedConfiguration === draftKey,
    actionPending,
    providerReady,
    egressReady,
    configurationChanged,
    selectProvider,
    selectModel,
    updateApiKey,
    setEgressConfirmed,
    keyMutation,
    testMutation,
    configurationMutation,
    reindexMutation,
  };
}

function configurationKey(provider: string, model: string) {
  return `${provider}:${model}`;
}

export function searchStatusRefreshInterval(status?: string) {
  return status === "stale" || status === "indexing" ? 2_000 : false;
}

export type SearchEmbeddingsController = ReturnType<typeof useSearchEmbeddingsPanelController>;
