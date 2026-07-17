import { ApiError } from "../../lib/api-client/client";

export function voiceStartError(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof DOMException) {
    if (error.name === "NotAllowedError") {
      return "Microphone permission was denied. Allow microphone access and try again.";
    }
    if (error.name === "NotFoundError") {
      return "No microphone was found. Connect one and try again.";
    }
    if (["AbortError", "NotReadableError"].includes(error.name)) {
      return "The microphone is unavailable or in use by another application.";
    }
  }
  return "Voice could not start. Please try again.";
}
