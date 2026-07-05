import { screen } from "@testing-library/react";

import AnalyticsDashboardPage from "./AnalyticsDashboardPage";
import { resetQueryClientForTests } from "../../app/query-client";
import type { AnalyticsDashboard } from "../../lib/api-client/analytics";
import { renderWithProviders } from "../../test/test-utils";

const dashboard: AnalyticsDashboard = {
  audience: "admin",
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

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("renders admin analytics metrics, product reuse and trends", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(dashboard)));

  renderWithProviders(<AnalyticsDashboardPage audience="admin" />, "/admin/analytics");

  expect(await screen.findByRole("heading", { name: "Admin Analytics" })).toBeVisible();
  expect(await screen.findByText("Arctic feedback product")).toBeVisible();
  expect(screen.getByText("Requester satisfaction")).toBeVisible();
  expect(screen.getByText("82 percent confidence")).toBeVisible();
  expect(screen.getAllByText("4.5")).toHaveLength(2);
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
        trends: [
          {
            title: "No trend baseline yet",
            summary: "No eligible tickets exist for this analytics scope.",
            signal: "neutral",
            confidence: 0.6,
          },
        ],
      }),
    ),
  );

  renderWithProviders(<AnalyticsDashboardPage audience="collection" />, "/collection/analytics");

  expect(await screen.findByRole("heading", { name: "Collection Analytics" })).toBeVisible();
  expect(await screen.findByText("No product reuse recorded.")).toBeVisible();
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
});

function jsonResponse(payload: unknown) {
  return { ok: true, json: () => Promise.resolve(payload) };
}
