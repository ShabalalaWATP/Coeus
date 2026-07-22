import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AnalyticsDashboardPage from "./AnalyticsDashboardPage";
import { resetQueryClientForTests } from "../../app/query-client";
import type { AnalyticsDashboard } from "../../lib/api-client/analytics";
import { renderWithProviders } from "../../test/test-utils";

const dashboard: AnalyticsDashboard = {
  audience: "rfa",
  metrics: {
    totalTickets: 2,
    activeTickets: 2,
    disseminations: 1,
    feedbackRequested: 1,
    feedbackSubmitted: 1,
    averageRating: 4.5,
    averageSearchCandidates: 2,
    rfaRoutes: 1,
    collectionRoutes: 1,
  },
  productReuse: [
    {
      productId: "product-1",
      reference: "PROD-1004",
      title: "Arctic feedback product",
      ownerTeam: "RFA",
      disseminationCount: 1,
      acceptedOfferCount: 0,
      feedbackCount: 1,
      averageRating: 4.5,
    },
  ],
  trends: [
    {
      title: "Requester satisfaction",
      summary: "Submitted feedback averages 4.5 out of 5.",
      signal: "positive",
      confidence: 0.82,
    },
  ],
};

const adminDashboard = {
  generatedAt: "2026-07-17T10:00:00Z",
  users: {
    total: 12,
    active: 10,
    disabled: 2,
    passwordResetRequired: 1,
    pendingRegistrations: 3,
    activeUsers30d: 8,
    roleCounts: [
      { role: "Administrator", count: 1 },
      { role: "Customer", count: 7 },
    ],
  },
  assistant: {
    provider: "gemini_api",
    model: "gemini-3.5-flash",
    apiKeyConfigured: true,
    chatTurns30d: 46,
  },
  search: {
    provider: "gemini_api",
    model: "gemini-embedding-2",
    apiKeyConfigured: true,
    indexStatus: "ready",
    searchRuns30d: 9,
    indexedProducts: 6,
    indexedPassages: 44,
    indexedRequests: 18,
    failedAssets: 1,
  },
  voice: {
    model: "gpt-realtime-mini",
    enabled: true,
    apiKeyConfigured: true,
    sessionsStarted30d: 5,
    users30d: 3,
  },
  audit: {
    windowDays: 30,
    retainedEvents: 120,
    events30d: 93,
    loginSuccesses30d: 31,
    loginFailures30d: 2,
    securityEvents30d: 4,
    configurationChanges30d: 6,
    coverageStartsAt: "2026-06-20T10:00:00Z",
    retentionLimitReached: true,
  },
  process: { remoteRequestsAdmitted: 51, remoteRequestsDenied: 2 },
};

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("renders aggregate admin analytics without intelligence detail", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(adminDashboard)));

  renderWithProviders(<AnalyticsDashboardPage audience="admin" />, "/admin/analytics");

  expect(await screen.findByRole("heading", { name: "Admin Analytics" })).toBeVisible();
  expect(screen.getByRole("link", { name: "Back to Admin" })).toHaveAttribute(
    "href",
    "/admin/overview",
  );
  expect(await screen.findByRole("heading", { name: "Account estate" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Text assistant" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Search & embeddings" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Voice" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Security and audit" })).toBeVisible();
  expect(screen.getByText(/audit retention limit has been reached/i)).toBeVisible();
  expect(screen.queryByText("Arctic feedback product")).not.toBeInTheDocument();
  expect(screen.queryByText("Requester satisfaction")).not.toBeInTheDocument();
});

test("renders empty admin activity and role states", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      jsonResponse({
        ...adminDashboard,
        users: { ...adminDashboard.users, roleCounts: [] },
        audit: {
          ...adminDashboard.audit,
          coverageStartsAt: null,
          retentionLimitReached: false,
        },
      }),
    ),
  );

  renderWithProviders(<AnalyticsDashboardPage audience="admin" />, "/admin/analytics");

  expect(await screen.findByText("No role assignments recorded.")).toBeVisible();
  expect(screen.getByText(/when the first event is recorded/)).toBeVisible();
  expect(screen.queryByText(/retention limit has been reached/)).not.toBeInTheDocument();
});

test("shows disabled and missing-key AI service states", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      jsonResponse({
        ...adminDashboard,
        assistant: { ...adminDashboard.assistant, apiKeyConfigured: false },
        voice: { ...adminDashboard.voice, apiKeyConfigured: false, enabled: false },
      }),
    ),
  );

  renderWithProviders(<AnalyticsDashboardPage audience="admin" />, "/admin/analytics");

  expect(await screen.findByText("Key missing")).toBeVisible();
  expect(screen.getByText("Disabled")).toBeVisible();
  expect(screen.getByText("Missing")).toBeVisible();
});

test("renders empty collection analytics without reuse records", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      jsonResponse({
        ...dashboard,
        audience: "collection",
        metrics: { ...dashboard.metrics, averageRating: null, totalTickets: 0 },
        productReuse: [],
        trends: [],
      }),
    ),
  );

  renderWithProviders(<AnalyticsDashboardPage audience="collection" />, "/collection/analytics");

  expect(await screen.findByRole("heading", { name: "Collection Analytics" })).toBeVisible();
  expect(await screen.findByText("No product reuse recorded.")).toBeVisible();
  expect(screen.getByText("No trend signals are available yet.")).toBeVisible();
  expect(screen.getByText("Pending")).toBeVisible();
});

test("renders pending product reuse feedback ratings", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      jsonResponse({
        ...dashboard,
        metrics: { ...dashboard.metrics, averageRating: null },
        productReuse: [{ ...dashboard.productReuse[0], averageRating: null }],
      }),
    ),
  );

  renderWithProviders(<AnalyticsDashboardPage audience="rfa" />, "/rfa/analytics");

  expect(await screen.findByRole("heading", { name: "RFA Analytics" })).toBeVisible();
  expect(await screen.findByText("Arctic feedback product")).toBeVisible();
  expect(screen.getAllByText("Pending")).toHaveLength(2);
  expect(screen.getAllByRole("progressbar")[0]).toHaveAttribute("aria-valuemax", "100");
});

test("renders an analytics error state", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
    }),
  );

  renderWithProviders(<AnalyticsDashboardPage audience="admin" />, "/admin/analytics");

  expect(
    await screen.findByText("Unable to load data", undefined, { timeout: 5000 }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
});

function jsonResponse(payload: unknown) {
  return { ok: true, json: () => Promise.resolve(payload) };
}
