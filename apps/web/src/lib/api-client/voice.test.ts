import { afterEach, expect, test, vi } from "vitest";

import { createVoiceSession } from "./voice";

afterEach(() => vi.unstubAllGlobals());

test("rejects an upstream voice answer without an admission token", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      headers: { get: () => null },
      ok: true,
      text: () => Promise.resolve("v=0\r\nm=audio answer"),
    }),
  );

  await expect(createVoiceSession("v=0\r\nm=audio offer", "csrf")).rejects.toThrow(
    "Voice session token missing",
  );
});
