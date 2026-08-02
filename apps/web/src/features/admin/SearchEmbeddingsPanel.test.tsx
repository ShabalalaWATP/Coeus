import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { SearchEmbeddingsPanel } from "./SearchEmbeddingsPanel";
import { resetQueryClientForTests } from "../../app/query-client";
import type { SearchEmbeddingState } from "../../lib/api-client/admin";
import { renderWithProviders } from "../../test/test-utils";

const baseState: SearchEmbeddingState = {
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
  releaseId: "mock:token-hash-v2:1536",
  evaluationStatus: "approved" as const,
  definitiveNoMatchEnabled: true,
};

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("explains automatic updates and hides advanced settings by default", async () => {
  mockState(baseState);
  renderWithProviders(<SearchEmbeddingsPanel csrfToken="csrf" />, "/admin/overview");

  expect(await screen.findByRole("heading", { name: "Search & embeddings" })).toBeVisible();
  expect(await screen.findByText("Preparing local search")).toBeVisible();
  expect(screen.getByText("Updating automatically")).toBeVisible();
  expect(screen.getByText(/You can leave this page/i)).toBeVisible();
  expect(screen.getByText("Requests prepared for matching")).toBeVisible();
  expect(screen.getByText("Change search service").closest("details")).not.toHaveAttribute("open");
  expect(screen.getByText(/No key or external network access is required/i)).not.toBeVisible();
  expect(screen.queryByLabelText("Embedding API key")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Rebuild search index/ })).not.toBeInTheDocument();
  expect(screen.getByText("Technical details").closest("details")).not.toHaveAttribute("open");
  expect(screen.getByText("1536 dimensions")).not.toBeVisible();
  expect(screen.getByText("mock:token-hash-v2:1536")).not.toBeVisible();
});

test("tests the selected Gemini draft before applying it", async () => {
  const user = userEvent.setup();
  let state = baseState;
  const fetchMock = vi.fn((url: string) => {
    if (url.endsWith("/api-key")) {
      state = { ...state, apiKeyConfigured: true };
      return ok(state);
    }
    if (url.endsWith("/test")) {
      return ok({
        ok: true,
        provider: "gemini_api",
        model: "gemini-embedding-2",
        message: "Search embedding connection succeeded.",
      });
    }
    if (url.endsWith("/configuration")) {
      state = {
        ...state,
        provider: "gemini_api",
        model: "gemini-embedding-2",
        apiKeyConfigured: true,
        availableModels: ["gemini-embedding-2"],
      };
    }
    return ok(state);
  });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<SearchEmbeddingsPanel csrfToken="csrf" />, "/admin/overview");

  await user.click(await screen.findByText("Change search service"));
  await user.click(await screen.findByRole("button", { name: /Gemini API/ }));
  const keyInput = screen.getByLabelText("Embedding API key");
  await user.type(keyInput, "search-key-value{Enter}");
  expect(await screen.findByText(/dedicated Gemini embeddings key is saved/i)).toBeVisible();
  await user.click(screen.getByRole("checkbox", { name: /synthetic connection-test phrase/i }));
  const apply = screen.getByRole("button", { name: /Apply retrieval configuration/ });
  expect(apply).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Test Gemini API" }));

  expect(await screen.findByText(/Connection OK: Gemini API · Gemini Embedding 2/)).toBeVisible();
  expect(apply).toBeEnabled();
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/admin/search-embeddings/test",
    expect.objectContaining({
      body: JSON.stringify({
        provider: "gemini_api",
        model: "gemini-embedding-2",
        confirmExternalEgress: true,
      }),
    }),
  );
  await user.click(apply);
  expect(await screen.findByText("Preparing Gemini search")).toBeVisible();
});

test("clears a successful draft test when the provider changes", async () => {
  const user = userEvent.setup();
  const ready = { ...baseState, apiKeyConfigured: true };
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      url.endsWith("/test")
        ? ok({
            ok: true,
            provider: "gemini_api",
            model: "gemini-embedding-2",
            message: "Search embedding connection succeeded.",
          })
        : ok(ready),
    ),
  );
  renderWithProviders(<SearchEmbeddingsPanel csrfToken="csrf" />, "/admin/overview");

  await user.click(await screen.findByText("Change search service"));
  await user.click(await screen.findByRole("button", { name: /Gemini API/ }));
  await user.click(screen.getByRole("checkbox", { name: /synthetic connection-test phrase/i }));
  await user.click(screen.getByRole("button", { name: "Test Gemini API" }));
  expect(await screen.findByText(/Connection OK/)).toBeVisible();
  await user.click(screen.getByRole("button", { name: /Local search/ }));

  expect(screen.queryByText(/Connection OK/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Tested gemini-embedding-2/)).not.toBeInTheDocument();
});

test("reports a failed candidate connection without authorising apply", async () => {
  const user = userEvent.setup();
  const ready = { ...baseState, apiKeyConfigured: true };
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      url.endsWith("/test")
        ? ok({
            ok: false,
            provider: "gemini_api",
            model: "gemini-embedding-2",
            message: "Search embedding connection is unavailable.",
          })
        : ok(ready),
    ),
  );
  renderWithProviders(<SearchEmbeddingsPanel csrfToken="csrf" />, "/admin/overview");

  await user.click(await screen.findByText("Change search service"));
  await user.click(await screen.findByRole("button", { name: /Gemini API/ }));
  await user.click(screen.getByRole("checkbox", { name: /synthetic connection-test phrase/i }));
  await user.click(screen.getByRole("button", { name: "Test Gemini API" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Connection failed");
  expect(screen.getByRole("alert")).toHaveTextContent("Replace the saved Gemini key");
  expect(screen.getByRole("button", { name: /Apply retrieval configuration/ })).toBeDisabled();
});

test("offers both supported Gemini embedding generations", async () => {
  const user = userEvent.setup();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok({ ...baseState, apiKeyConfigured: true })));
  renderWithProviders(<SearchEmbeddingsPanel csrfToken="csrf" />, "/admin/overview");

  await user.click(await screen.findByText("Change search service"));
  await user.click(await screen.findByRole("button", { name: /Gemini API/ }));

  expect(screen.getByRole("radio", { name: /Gemini Embedding 2/ })).toBeVisible();
  expect(screen.getByRole("radio", { name: /Gemini Embedding 001/ })).toBeVisible();
});

test("starts a rebuild and presents degraded status", async () => {
  const user = userEvent.setup();
  const degraded = {
    ...baseState,
    indexStatus: "failed",
    degradedReason: "provider_unavailable",
  };
  const fetchMock = vi.fn().mockResolvedValue(ok(degraded));
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<SearchEmbeddingsPanel csrfToken="csrf" />, "/admin/overview");

  expect(await screen.findByText(/configured search service could not be reached/i)).toBeVisible();
  await user.click(screen.getByRole("button", { name: /Try automatic update again/ }));
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

test("locks configuration controls while a connection test is pending", async () => {
  const user = userEvent.setup();
  let resolveTest: ((value: Response) => void) | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      url.endsWith("/test")
        ? new Promise<Response>((resolve) => {
            resolveTest = resolve;
          })
        : Promise.resolve(ok(baseState)),
    ),
  );
  renderWithProviders(<SearchEmbeddingsPanel csrfToken="csrf" />, "/admin/overview");

  await user.click(await screen.findByText("Change search service"));
  await user.click(await screen.findByRole("button", { name: "Test Local search" }));
  await waitFor(() => expect(screen.getByRole("button", { name: /Gemini API/ })).toBeDisabled());
  expect(screen.queryByRole("button", { name: /automatic update again/ })).not.toBeInTheDocument();
  resolveTest?.(
    ok({
      ok: true,
      provider: "mock",
      model: "token-hash-v2",
      message: "Search embedding connection succeeded.",
    }),
  );
  expect(await screen.findByText(/Connection OK/)).toBeVisible();
});

test("keeps an unknown persisted provider and model visible", async () => {
  const user = userEvent.setup();
  const custom = {
    ...baseState,
    provider: "custom",
    model: "custom-embedding-model",
    availableProviders: ["custom"],
    availableModels: ["custom-embedding-model"],
  };
  mockState(custom);
  renderWithProviders(<SearchEmbeddingsPanel csrfToken="csrf" />, "/admin/overview");

  await user.click(await screen.findByText("Change search service"));
  expect(await screen.findByRole("button", { name: "custom Live" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(screen.getByRole("radio", { name: /custom-embedding-model/ })).toBeChecked();
  expect(screen.getByRole("button", { name: "Test custom" })).toBeDisabled();
});

test("reports a rejected dedicated-key save", async () => {
  const user = userEvent.setup();
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      url.endsWith("/api-key")
        ? Promise.resolve({
            ok: false,
            status: 422,
            json: () => Promise.resolve({ error: { code: "invalid_api_key" } }),
          })
        : Promise.resolve(ok(baseState)),
    ),
  );
  renderWithProviders(<SearchEmbeddingsPanel csrfToken="csrf" />, "/admin/overview");

  await user.click(await screen.findByText("Change search service"));
  await user.click(await screen.findByRole("button", { name: /Gemini API/ }));
  await user.type(screen.getByLabelText("Embedding API key"), "rejected-search-key{Enter}");
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Search settings could not be updated.",
  );
});

test("reports a rejected index rebuild", async () => {
  const user = userEvent.setup();
  const failed = { ...baseState, indexStatus: "failed", degradedReason: "provider_unavailable" };
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      url.endsWith("/reindex")
        ? Promise.resolve({
            ok: false,
            status: 500,
            json: () => Promise.resolve({ error: { code: "reindex_failed" } }),
          })
        : Promise.resolve(ok(failed)),
    ),
  );
  renderWithProviders(<SearchEmbeddingsPanel csrfToken="csrf" />, "/admin/overview");

  await user.click(await screen.findByRole("button", { name: /Try automatic update again/ }));
  expect(
    await screen.findByText("Istari could not restart the search library update."),
  ).toBeVisible();
});

function mockState(state: SearchEmbeddingState) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok(state)));
}

function ok(payload: unknown): Response {
  return {
    ok: true,
    json: () => Promise.resolve(payload),
  } as Response;
}
