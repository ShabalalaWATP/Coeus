import { afterEach, expect, test, vi } from "vitest";

import { createVoiceSession, testAdminVoiceConnection } from "./voice";

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

test("starts voice with the current authorised ticket context", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    headers: { get: () => "voice-token" },
    ok: true,
    text: () => Promise.resolve("v=0\r\nm=audio answer"),
  });
  vi.stubGlobal("fetch", fetchMock);

  await createVoiceSession("v=0\r\nm=audio offer", "csrf", "ticket/id");

  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/voice/session?ticketId=ticket%2Fid",
    expect.objectContaining({ method: "POST" }),
  );
});

test("tests the dedicated admin voice configuration with CSRF", async () => {
  const result = {
    ok: true,
    provider: "openai_realtime",
    model: "gpt-realtime-mini",
    message: "OpenAI Realtime accepted gpt-realtime-mini.",
  };
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(result) });
  vi.stubGlobal("fetch", fetchMock);

  await expect(testAdminVoiceConnection("csrf")).resolves.toEqual(result);
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/admin/voice-model/test",
    expect.objectContaining({ headers: { "X-CSRF-Token": "csrf" }, method: "POST" }),
  );
});
