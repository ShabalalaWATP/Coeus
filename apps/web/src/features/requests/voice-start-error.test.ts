import { describe, expect, test } from "vitest";

import { ApiError } from "../../lib/api-client/client";
import { voiceStartError } from "./voice-start-error";

describe("voiceStartError", () => {
  test.each([
    ["NotAllowedError", "Microphone permission was denied"],
    ["NotFoundError", "No microphone was found"],
    ["NotReadableError", "microphone is unavailable or in use"],
    ["AbortError", "microphone is unavailable or in use"],
  ])("maps %s microphone failures accurately", (name, message) => {
    const error = new DOMException("device detail that must not be shown", name);

    expect(voiceStartError(error)).toContain(message);
    expect(voiceStartError(error)).not.toContain("device detail");
  });

  test("surfaces only the sanitised message from an API error", () => {
    const error = new ApiError(
      503,
      "voice_provider_credentials_rejected",
      "OpenAI rejected the configured Realtime API key.",
    );

    expect(voiceStartError(error)).toBe("OpenAI rejected the configured Realtime API key.");
  });

  test("does not expose unknown error details or blame microphone permission", () => {
    const message = voiceStartError(new Error("internal browser detail"));

    expect(message).toBe("Voice could not start. Please try again.");
    expect(message).not.toContain("permission");
    expect(message).not.toContain("internal browser detail");
  });

  test("uses the generic response for other DOM exceptions", () => {
    expect(voiceStartError(new DOMException("detail", "SecurityError"))).toBe(
      "Voice could not start. Please try again.",
    );
  });
});
