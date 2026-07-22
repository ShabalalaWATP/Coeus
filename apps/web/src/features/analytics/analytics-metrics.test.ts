import { describe, expect, test } from "vitest";

import { deriveAnalytics, operationalAttention } from "./analytics-metrics";
import type { AnalyticsDashboard } from "../../lib/api-client/analytics";

const dashboard: AnalyticsDashboard = {
  audience: "admin",
  metrics: {
    totalTickets: 10,
    activeTickets: 7,
    disseminations: 5,
    feedbackRequested: 4,
    feedbackSubmitted: 2,
    averageRating: 4,
    averageSearchCandidates: 3,
    rfaRoutes: 4,
    collectionRoutes: 3,
  },
  productReuse: [],
  trends: [],
};

describe("analytics derivation", () => {
  test("derives rates from the authorised aggregate", () => {
    expect(deriveAnalytics(dashboard)).toEqual({
      activeRate: 70,
      nonActiveRate: 30,
      nonActiveTickets: 3,
      disseminationRate: 0.5,
      feedbackOutstanding: 2,
      feedbackResponseRate: 50,
      routeCoverage: 70,
      routedTickets: 7,
      unroutedTickets: 3,
    });
    expect(operationalAttention(dashboard, deriveAnalytics(dashboard))).toEqual([
      {
        label: "Active workload is elevated",
        detail: "7 of 10 requests remain active.",
        tone: "watch",
      },
      {
        label: "Feedback coverage gap",
        detail: "2 requested responses are still outstanding.",
        tone: "watch",
      },
    ]);
  });

  test("handles an empty scope without dividing by zero", () => {
    const empty = {
      ...dashboard,
      metrics: {
        ...dashboard.metrics,
        totalTickets: 0,
        activeTickets: 0,
        feedbackRequested: 0,
        feedbackSubmitted: 0,
      },
    };
    const derived = deriveAnalytics(empty);
    expect(derived.activeRate).toBe(0);
    expect(derived.disseminationRate).toBe(0);
    expect(operationalAttention(empty, derived)[0].label).toBe("No workload baseline");
  });

  test("recognises a balanced scope and a missing search baseline", () => {
    const balanced = {
      ...dashboard,
      metrics: {
        ...dashboard.metrics,
        activeTickets: 2,
        feedbackSubmitted: 4,
      },
    };
    expect(operationalAttention(balanced, deriveAnalytics(balanced))[0].tone).toBe("good");
    const noSearch = {
      ...balanced,
      metrics: { ...balanced.metrics, averageSearchCandidates: null },
    };
    expect(operationalAttention(noSearch, deriveAnalytics(noSearch))[0].label).toBe(
      "Search evidence is incomplete",
    );
    const oneOutstanding = {
      ...balanced,
      metrics: { ...balanced.metrics, feedbackSubmitted: 3 },
    };
    expect(operationalAttention(oneOutstanding, deriveAnalytics(oneOutstanding))[0].detail).toBe(
      "1 requested response is still outstanding.",
    );
  });
});
