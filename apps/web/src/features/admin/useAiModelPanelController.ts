import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { type ModelNote } from "./ai-model-panel-utils";
import {
  addCustomAiModel,
  configureAiApiKey,
  getAiModelState,
  refreshAiModels,
  selectAiModel,
  selectAiProvider,
  testAiConnection,
  type AiConnectionTest,
  type AiModelState,
} from "../../lib/api-client/admin";
import { actionErrorMessage, useActionError } from "../../lib/mutations/action-error";

export function useAiModelPanelController(csrfToken: string) {
  const queryClient = useQueryClient();
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [testResult, setTestResult] = useState<AiConnectionTest | null>(null);
  const [modelNote, setModelNote] = useState<ModelNote | null>(null);
  const [confirmingActivation, setConfirmingActivation] = useState(false);
  const [testedConfiguration, setTestedConfiguration] = useState<string | null>(null);
  const activateButtonRef = useRef<HTMLButtonElement>(null);
  const { actionError, clearActionError, failActionWith } = useActionError();
  const stateQuery = useQuery({ queryKey: ["ai-model"], queryFn: getAiModelState });
  const state = stateQuery.data;
  const providerName = selectedProvider ?? state?.provider ?? "gemini_api";
  const provider = state?.providers.find((entry) => entry.name === providerName);
  const applyState = (next: AiModelState) => queryClient.setQueryData(["ai-model"], next);
  const resetTest = () => {
    clearActionError();
    setTestResult(null);
    setTestedConfiguration(null);
  };
  const updateApiKey = (value: string) => {
    setApiKey(value);
    resetTest();
  };
  const modelMutation = useMutation({
    mutationFn: (model: string) => selectAiModel(model, providerName, csrfToken),
    onError: failActionWith("The model could not be changed. Refresh and try again."),
    onMutate: resetTest,
    onSuccess: (next: AiModelState) => {
      setSelectedModel(null);
      applyState(next);
    },
  });
  const keyMutation = useMutation({
    mutationFn: (key: string) => configureAiApiKey(key, providerName, csrfToken),
    onError: failActionWith("The API key could not be saved. Check the key and try again."),
    onMutate: resetTest,
    onSuccess: (next: AiModelState) => {
      setApiKey("");
      applyState(next);
    },
  });
  const testMutation = useMutation({
    mutationFn: () => testAiConnection(providerName, csrfToken),
    onError: failActionWith("The connection test could not be run."),
    onMutate: resetTest,
    onSuccess: (result) => {
      setTestResult(result);
      setTestedConfiguration(result.ok ? configurationKey(providerName, result.model) : null);
    },
  });
  const activateMutation = useMutation({
    mutationFn: () => selectAiProvider(providerName, csrfToken),
    onError: failActionWith("The provider could not be activated."),
    onMutate: clearActionError,
    onSuccess: (next: AiModelState) => {
      setConfirmingActivation(false);
      applyState(next);
    },
  });
  const refreshMutation = useMutation({
    mutationFn: () => refreshAiModels(providerName, csrfToken),
    onMutate: () => {
      resetTest();
      setModelNote(null);
    },
    onError: (error) =>
      setModelNote({ tone: "fail", text: actionErrorMessage(error, "Could not refresh models.") }),
    onSuccess: (next: AiModelState) => {
      applyState(next);
      const entry = next.providers.find((item) => item.name === providerName);
      setModelNote({
        tone: "ok",
        text: `${entry?.models.length ?? 0} models available for ${entry?.label ?? providerName}.`,
      });
    },
  });
  const customMutation = useMutation({
    mutationFn: (model: string) => addCustomAiModel(providerName, model, csrfToken),
    onMutate: () => {
      resetTest();
      setModelNote(null);
    },
    onError: (error) =>
      setModelNote({
        tone: "fail",
        text: actionErrorMessage(error, "That model ID could not be added."),
      }),
    onSuccess: (next: AiModelState, model: string) => {
      applyState(next);
      setSelectedModel(model);
      setModelNote({
        tone: "ok",
        text: `Added ${model}. Choose Apply model to make it active.`,
      });
    },
  });
  const pickProvider = (name: string) => {
    setSelectedProvider(name);
    setSelectedModel(null);
    setApiKey("");
    setModelNote(null);
    setConfirmingActivation(false);
    resetTest();
  };
  const activeChoice = selectedModel ?? provider?.activeModel ?? "";
  const currentConfiguration = provider ? configurationKey(provider.name, activeChoice) : "";
  const configurationPending = [
    modelMutation,
    keyMutation,
    testMutation,
    activateMutation,
    refreshMutation,
    customMutation,
  ].some((mutation) => mutation.isPending);
  return {
    stateQuery,
    state,
    providerName,
    provider,
    apiKey,
    setApiKey: updateApiKey,
    testResult,
    modelNote,
    confirmingActivation,
    setConfirmingActivation,
    activateButtonRef,
    actionError,
    modelMutation,
    keyMutation,
    testMutation,
    activateMutation,
    refreshMutation,
    customMutation,
    pickProvider,
    activeChoice,
    setSelectedModel,
    setTestResult,
    setTestedConfiguration,
    isLive: provider?.name === state?.provider,
    isMock: provider?.name === "mock",
    activationTested: testedConfiguration === currentConfiguration,
    testedConfiguration,
    testReady: selectedModel === null && apiKey.trim() === "" && Boolean(provider),
    configurationPending,
  };
}

function configurationKey(provider: string, model: string) {
  return `${provider}:${model}`;
}
