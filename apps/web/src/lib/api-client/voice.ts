import { apiRequest, apiRequestJson } from "./client";

export type VoiceModelState = {
  model: string;
  availableModels: string[];
  enabled: boolean;
  apiKeyConfigured: boolean;
};

export function getAdminVoiceModel(): Promise<VoiceModelState> {
  return apiRequestJson<VoiceModelState>("/api/v1/admin/voice-model", { method: "GET" });
}

export function updateAdminVoiceModel(
  model: string,
  enabled: boolean,
  csrfToken: string,
): Promise<VoiceModelState> {
  return apiRequestJson<VoiceModelState>("/api/v1/admin/voice-model", {
    body: JSON.stringify({ model, enabled }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "PUT",
  });
}

export function updateAdminVoiceApiKey(
  apiKey: string,
  csrfToken: string,
): Promise<VoiceModelState> {
  return apiRequestJson<VoiceModelState>("/api/v1/admin/voice-model/api-key", {
    body: JSON.stringify({ apiKey }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "PUT",
  });
}

export function getVoiceConfig(): Promise<VoiceModelState> {
  return apiRequestJson<VoiceModelState>("/api/v1/voice/config", { method: "GET" });
}

export async function createVoiceSession(
  sdp: string,
  csrfToken: string,
): Promise<{ answer: string; token: string }> {
  const response = await apiRequest("/api/v1/voice/session", {
    body: sdp,
    headers: { "Content-Type": "application/sdp", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
  const token = response.headers.get("X-Voice-Session-Token");
  if (!token) throw new Error("Voice session token missing");
  return { answer: await response.text(), token };
}

export async function releaseVoiceSession(token: string, csrfToken: string): Promise<void> {
  await apiRequest(`/api/v1/voice/session/${encodeURIComponent(token)}`, {
    headers: { "X-CSRF-Token": csrfToken },
    method: "DELETE",
  });
}
