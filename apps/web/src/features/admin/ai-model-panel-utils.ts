import { ApiError } from "../../lib/api-client/client";
import type { AiProviderState } from "../../lib/api-client/admin";

export type ModelNote = { tone: "ok" | "fail"; text: string };

export type ProviderStatus = {
  label: string;
  tone: "live" | "local" | "ready" | "empty";
};

export function providerStatus(entry: AiProviderState, liveProvider: string): ProviderStatus {
  if (entry.name === liveProvider) return { label: "Live", tone: "live" };
  if (entry.name === "mock") return { label: "Local", tone: "local" };
  if (entry.apiKeyConfigured) return { label: "Key set", tone: "ready" };
  return { label: "No key", tone: "empty" };
}

export function errorText(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}
