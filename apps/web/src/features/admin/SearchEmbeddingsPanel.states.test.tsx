import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { resetQueryClientForTests } from "../../app/query-client";
import type { SearchEmbeddingState } from "../../lib/api-client/admin";
import { renderWithProviders } from "../../test/test-utils";
import { SearchEmbeddingsPanel } from "./SearchEmbeddingsPanel";

const state: SearchEmbeddingState = {
  provider: "mock",
  model: "token-hash-v2",
  dimensions: 1536,
  apiKeyConfigured: true,
  availableProviders: ["mock", "gemini_api"],
  availableModels: ["token-hash-v2"],
  indexStatus: "ready",
  indexGeneration: 2,
  productCount: 8,
  chunkCount: 31,
  ticketCount: 12,
  failedAssetCount: 0,
  corpusVersion: "current-corpus",
  spaceId: "mock:token-hash-v2:1536:g2",
  changedBy: "admin1",
  changedAt: "2026-08-01T12:00:00Z",
  lastIndexedAt: "2026-08-01T12:05:00Z",
  degradedReason: null,
  releaseId: "mock:token-hash-v2:1536",
  evaluationStatus: "approved",
  definitiveNoMatchEnabled: true,
};

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("explains an automatic Gemini update and separates pending quality checks", async () => {
  const gemini: SearchEmbeddingState = {
    ...state,
    provider: "gemini_api",
    model: "gemini-embedding-2",
    availableModels: ["gemini-embedding-2"],
    indexStatus: "indexing",
    evaluationStatus: "required",
    definitiveNoMatchEnabled: false,
  };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(ok(gemini)));

  renderWithProviders(<SearchEmbeddingsPanel csrfToken="csrf" />, "/admin/overview");

  expect(await screen.findByText("Preparing Gemini search")).toBeVisible();
  expect(screen.getByText(/updating the search library automatically/i)).toBeVisible();
  expect(screen.getAllByText("Quality checks pending")).toHaveLength(2);
  expect(screen.getByText(/Search works now/i)).toBeVisible();
  expect(screen.queryByRole("button", { name: /update again/i })).not.toBeInTheDocument();
  expect(screen.queryByText("admin1")).not.toBeInTheDocument();
  expect(screen.getByText("Last updated").parentElement).not.toHaveTextContent("Never");
});

test("keeps checking while an automatic update is queued", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(ok({ ...state, indexStatus: "stale" }))
    .mockResolvedValue(ok(state));
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<SearchEmbeddingsPanel csrfToken="csrf" />, "/admin/overview");

  expect(await screen.findByText("Preparing local search")).toBeVisible();
  expect(await screen.findByText("Local search is ready", {}, { timeout: 3_500 })).toBeVisible();
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

test("reports transport failure for the selected candidate test", async () => {
  const user = userEvent.setup();
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      url.endsWith("/test") ? Promise.reject(new Error("offline")) : Promise.resolve(ok(state)),
    ),
  );
  renderWithProviders(<SearchEmbeddingsPanel csrfToken="csrf" />, "/admin/overview");

  await user.click(await screen.findByText("Change search service"));
  await user.click(await screen.findByRole("button", { name: "Test Local search" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The selected search connection could not be tested.",
  );
});

test("reports a rejected apply after an exact Gemini draft test", async () => {
  const user = userEvent.setup();
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.endsWith("/test")) {
        return Promise.resolve(
          ok({
            ok: true,
            provider: "gemini_api",
            model: "gemini-embedding-2",
            message: "Search embedding connection succeeded.",
          }),
        );
      }
      if (url.endsWith("/configuration")) {
        return Promise.resolve({
          ok: false,
          status: 409,
          json: () => Promise.resolve({ error: { code: "search_reindex_active" } }),
        });
      }
      return Promise.resolve(ok(state));
    }),
  );
  renderWithProviders(<SearchEmbeddingsPanel csrfToken="csrf" />, "/admin/overview");

  await user.click(await screen.findByText("Change search service"));
  await user.click(await screen.findByRole("button", { name: /Gemini API/ }));
  await user.click(screen.getByRole("checkbox", { name: /synthetic connection-test phrase/i }));
  await user.click(screen.getByRole("button", { name: "Test Gemini API" }));
  await user.click(await screen.findByRole("button", { name: /Apply retrieval configuration/ }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Search settings could not be updated.",
  );
});

function ok(payload: unknown): Response {
  return { ok: true, json: () => Promise.resolve(payload) } as Response;
}
