import { apiRequestJson } from "./client";

export type AiModelState = {
  provider: string;
  activeModel: string;
  availableModels: string[];
};

export async function getAiModelState(): Promise<AiModelState> {
  return apiRequestJson<AiModelState>("/api/v1/admin/ai-model", { method: "GET" });
}

export async function selectAiModel(model: string, csrfToken: string): Promise<AiModelState> {
  return apiRequestJson<AiModelState>("/api/v1/admin/ai-model", {
    body: JSON.stringify({ model }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "PUT",
  });
}
