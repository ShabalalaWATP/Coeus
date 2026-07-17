import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SearchEmbeddingsPanel } from "./SearchEmbeddingsPanel";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const baseState = {
  provider: "mock",
  model: "token-hash-v2",
  dimensions: 1536,
  apiKeyConfigured: false,
  availableProviders: ["mock", "gemini_api"],
  availableModels: ["token-hash-v2"],
  indexStatus: "stale",
  indexGeneration: 1,
  productCount: 8,
  chunkCount: 31,
  ticketCount: 12,
  failedAssetCount: 2,
  corpusVersion: "abc123corpus",
  spaceId: "mock:token-hash-v2:1536:g1",
  changedBy: null,
  changedAt: null,
  lastIndexedAt: null,
  degradedReason: null,
};

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("shows the independent provider, model and index provenance", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(baseState) }),
  );
  renderWithProviders(<SearchEmbeddingsPanel csrfToken="csrf" />, "/admin/overview");

  expect(await screen.findByRole("heading", { name: "Search & embeddings" })).toBeVisible();
  expect(await screen.findByText("1536 dimensions")).toBeVisible();
  expect(screen.getByText("31")).toBeVisible();
  expect(screen.getByText(/not shared with text chat or voice/i)).toBeVisible();
});

test("requires explicit egress consent before selecting Gemini", async () => {
  const user = userEvent.setup();
  let state = baseState;
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.endsWith("/api-key")) {
      state = { ...state, apiKeyConfigured: true };
    }
    if (url.endsWith("/configuration")) {
      state = {
        ...state,
        provider: "gemini_api",
        model: "gemini-embedding-2",
        indexGeneration: 2,
      };
    }
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve(init?.method === "POST" ? { ok: true } : state),
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<SearchEmbeddingsPanel csrfToken="csrf" />, "/admin/overview");

  const keyInput = await screen.findByLabelText("Embedding API key");
  await user.type(keyInput, "search-key-value");
  await user.click(screen.getByRole("button", { name: /Save search key/ }));
  await waitFor(() => expect(screen.getByLabelText("Embedding provider")).toBeEnabled());
  await user.selectOptions(screen.getByLabelText("Embedding provider"), "gemini_api");

  const save = screen.getByRole("button", { name: /Save retrieval configuration/ });
  expect(save).toBeDisabled();
  await user.click(screen.getByRole("checkbox", { name: /synthetic Store text/ }));
  expect(save).toBeEnabled();
  await user.click(save);

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/admin/search-embeddings/configuration",
      expect.objectContaining({
        body: JSON.stringify({
          provider: "gemini_api",
          model: "gemini-embedding-2",
          confirmExternalEgress: true,
        }),
      }),
    ),
  );
});

test("starts a controlled index rebuild and displays degraded state", async () => {
  const user = userEvent.setup();
  const degraded = { ...baseState, degradedReason: "provider_unavailable" };
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(degraded),
  });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<SearchEmbeddingsPanel csrfToken="csrf" />, "/admin/overview");

  expect(await screen.findByText(/Retrieval is degraded: provider unavailable/)).toBeVisible();
  await user.click(screen.getByRole("button", { name: /Rebuild search index/ }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/admin/search-embeddings/reindex",
      expect.objectContaining({ method: "POST" }),
    ),
  );
});

test("shows loading and a fail-closed settings error", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  renderWithProviders(<SearchEmbeddingsPanel csrfToken="csrf" />, "/admin/overview");

  expect(screen.getByRole("status")).toHaveTextContent("Loading search settings");
  expect(await screen.findByRole("alert", {}, { timeout: 3_000 })).toHaveTextContent(
    "Search settings are unavailable",
  );
});

test("tests the active provider and locks an in-progress rebuild", async () => {
  const user = userEvent.setup();
  const indexing = { ...baseState, indexStatus: "indexing" };
  const fetchMock = vi.fn((url: string) =>
    Promise.resolve({
      ok: true,
      json: () =>
        Promise.resolve(
          url.endsWith("/test")
            ? { ok: true, message: "Embedding connection succeeded." }
            : indexing,
        ),
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<SearchEmbeddingsPanel csrfToken="csrf" />, "/admin/overview");

  expect(await screen.findByRole("button", { name: "Re-indexing…" })).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Test connection" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Embedding connection succeeded.");
});

test("uses provider model fallback and reports rejected mutations", async () => {
  const user = userEvent.setup();
  const custom = {
    ...baseState,
    provider: "custom",
    model: "custom-embedding-model",
    availableProviders: ["custom"],
    availableModels: ["custom-embedding-model"],
  };
  const fetchMock = vi.fn((url: string) =>
    Promise.resolve(
      url.endsWith("/api-key")
        ? {
            ok: false,
            status: 500,
            json: () => Promise.resolve({ error: { code: "key_failed", message: "Key failed." } }),
          }
        : { ok: true, json: () => Promise.resolve(custom) },
    ),
  );
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<SearchEmbeddingsPanel csrfToken="csrf" />, "/admin/overview");

  expect(await screen.findByRole("option", { name: "custom-embedding-model" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Test connection" })).toBeDisabled();
  await user.type(screen.getByLabelText("Embedding API key"), "rejected-search-key");
  await user.click(screen.getByRole("button", { name: "Save search key" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Search settings could not be updated.",
  );
});

test("reports a rejected index rebuild", async () => {
  const user = userEvent.setup();
  const fetchMock = vi.fn((url: string) =>
    Promise.resolve(
      url.endsWith("/reindex")
        ? {
            ok: false,
            status: 500,
            json: () =>
              Promise.resolve({ error: { code: "reindex_failed", message: "Re-index failed." } }),
          }
        : { ok: true, json: () => Promise.resolve(baseState) },
    ),
  );
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<SearchEmbeddingsPanel csrfToken="csrf" />, "/admin/overview");

  await user.click(await screen.findByRole("button", { name: "Rebuild search index" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Search settings could not be updated.",
  );
});
