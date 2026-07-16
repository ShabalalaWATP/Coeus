import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { VoiceModelPanel } from "./VoiceModelPanel";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const state = {
  model: "gpt-realtime-2.1-mini",
  availableModels: ["gpt-realtime-2.1-mini"],
  enabled: false,
  apiKeyConfigured: true,
};

afterEach(() => vi.unstubAllGlobals());
beforeEach(() => resetQueryClientForTests());

test("requires a dedicated admin-entered key before voice can be enabled", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(response({ ...state, apiKeyConfigured: false })),
  );
  renderWithProviders(<VoiceModelPanel csrfToken="csrf" />, "/admin/overview");

  expect(await screen.findByRole("checkbox")).toBeDisabled();
  expect(screen.getByText(/Save the dedicated Voice API key/)).toBeVisible();
  expect(screen.getByText(/separate from every text-chat provider key/)).toBeVisible();
  expect(screen.getByRole("button", { name: "Save voice key" })).toBeDisabled();
});

test("saves the voice key through its separate admin endpoint", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(response({ ...state, apiKeyConfigured: false }))
    .mockResolvedValueOnce(response(state));
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<VoiceModelPanel csrfToken="csrf" />, "/admin/overview");

  await userEvent.type(await screen.findByLabelText("OpenAI Realtime key"), "sk-voice-only-key");
  await userEvent.click(screen.getByRole("button", { name: "Save voice key" }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  expect(fetchMock).toHaveBeenLastCalledWith(
    "http://127.0.0.1:8001/api/v1/admin/voice-model/api-key",
    expect.objectContaining({
      body: JSON.stringify({ apiKey: "sk-voice-only-key" }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
      method: "PUT",
    }),
  );
});

test("shows a bounded error when the dedicated voice key cannot be saved", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValueOnce(response(state)).mockResolvedValueOnce(failedResponse()),
  );
  renderWithProviders(<VoiceModelPanel csrfToken="csrf" />, "/admin/overview");

  await userEvent.type(await screen.findByLabelText("OpenAI Realtime key"), "sk-voice-only-key");
  await userEvent.click(screen.getByRole("button", { name: "Save voice key" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The Voice API key could not be saved.",
  );
  expect(screen.queryByText("provider detail")).not.toBeInTheDocument();
});

test("locks the voice controls while key and model changes are being saved", async () => {
  const pendingKey = deferred<ReturnType<typeof response>>();
  const pendingSettings = deferred<ReturnType<typeof response>>();
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce(response(state))
      .mockReturnValueOnce(pendingKey.promise)
      .mockReturnValueOnce(pendingSettings.promise),
  );
  renderWithProviders(<VoiceModelPanel csrfToken="csrf" />, "/admin/overview");

  await userEvent.type(await screen.findByLabelText("OpenAI Realtime key"), "sk-voice-only-key");
  await userEvent.click(screen.getByRole("button", { name: "Save voice key" }));
  expect(await screen.findByRole("button", { name: "Saving…" })).toBeDisabled();
  pendingKey.resolve(response(state));
  expect(await screen.findByRole("button", { name: "Save voice key" })).toBeDisabled();

  await userEvent.click(screen.getByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: "Save voice settings" }));
  expect(await screen.findByRole("button", { name: "Saving…" })).toBeDisabled();
  pendingSettings.resolve(response({ ...state, enabled: true }));
  expect(await screen.findByText("Voice settings saved.")).toBeVisible();
});

test("enables and saves the separately configured voice model", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(response(state))
    .mockResolvedValueOnce(response({ ...state, enabled: true }));
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<VoiceModelPanel csrfToken="csrf" />, "/admin/overview");

  await userEvent.click(await screen.findByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: "Save voice settings" }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  expect(fetchMock).toHaveBeenLastCalledWith(
    "http://127.0.0.1:8001/api/v1/admin/voice-model",
    expect.objectContaining({
      body: JSON.stringify({ model: "gpt-realtime-2.1-mini", enabled: true }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
      method: "PUT",
    }),
  );
  expect(await screen.findByText("Voice settings saved.")).toBeVisible();
});

test("shows query and save failures without exposing provider details", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("provider detail")));
  const first = renderWithProviders(<VoiceModelPanel csrfToken="csrf" />, "/admin/overview");
  expect(await screen.findByText("Voice settings are unavailable.")).toBeVisible();
  first.unmount();
  resetQueryClientForTests();

  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValueOnce(response(state)).mockResolvedValueOnce(failedResponse()),
  );
  renderWithProviders(<VoiceModelPanel csrfToken="csrf" />, "/admin/overview");
  await userEvent.click(await screen.findByRole("checkbox"));
  await userEvent.click(screen.getByRole("button", { name: "Save voice settings" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("could not be saved");
  expect(screen.queryByText("provider detail")).not.toBeInTheDocument();
});

function response(payload: object) {
  return { ok: true, json: () => Promise.resolve(payload) };
}

function failedResponse() {
  return {
    ok: false,
    status: 500,
    json: () => Promise.resolve({ error: { code: "upstream", message: "provider detail" } }),
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}
