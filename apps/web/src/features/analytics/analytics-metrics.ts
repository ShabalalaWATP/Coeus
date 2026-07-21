import type { AnalyticsDashboard } from "../../lib/api-client/analytics";

export type DerivedAnalytics = {
  activeRate: number;
  nonActiveRate: number;
  nonActiveTickets: number;
  disseminationRate: number;
  feedbackOutstanding: number;
  feedbackResponseRate: number;
  routeCoverage: number;
  routedTickets: number;
  unroutedTickets: number;
};

export function deriveAnalytics(dashboard: AnalyticsDashboard): DerivedAnalytics {
  const metrics = dashboard.metrics;
  const nonActiveTickets = Math.max(0, metrics.totalTickets - metrics.activeTickets);
  const routedTickets = Math.min(
    metrics.totalTickets,
    metrics.rfaRoutes + metrics.collectionRoutes,
  );
  return {
    activeRate: percent(metrics.activeTickets, metrics.totalTickets),
    nonActiveRate: percent(nonActiveTickets, metrics.totalTickets),
    nonActiveTickets,
    disseminationRate:
      metrics.totalTickets === 0 ? 0 : metrics.disseminations / metrics.totalTickets,
    feedbackOutstanding: Math.max(0, metrics.feedbackRequested - metrics.feedbackSubmitted),
    feedbackResponseRate: percent(metrics.feedbackSubmitted, metrics.feedbackRequested),
    routeCoverage: percent(routedTickets, metrics.totalTickets),
    routedTickets,
    unroutedTickets: Math.max(0, metrics.totalTickets - routedTickets),
  };
}

export function operationalAttention(
  dashboard: AnalyticsDashboard,
  derived: DerivedAnalytics,
): { detail: string; label: string; tone: "good" | "watch" }[] {
  if (dashboard.metrics.totalTickets === 0) {
    return [
      {
        detail: "Create and route requests before using this dashboard as a performance baseline.",
        label: "No workload baseline",
        tone: "watch",
      },
    ];
  }
  const items: { detail: string; label: string; tone: "good" | "watch" }[] = [];
  if (derived.activeRate >= 70) {
    items.push({
      detail: `${dashboard.metrics.activeTickets} of ${dashboard.metrics.totalTickets} requests remain active.`,
      label: "Active workload is elevated",
      tone: "watch",
    });
  }
  if (derived.feedbackOutstanding > 0) {
    items.push({
      detail: `${derived.feedbackOutstanding} requested response${derived.feedbackOutstanding === 1 ? " is" : "s are"} still outstanding.`,
      label: "Feedback coverage gap",
      tone: "watch",
    });
  }
  if (dashboard.metrics.averageSearchCandidates === null) {
    items.push({
      detail: "Run RFI searches to establish a retrieval-candidate baseline.",
      label: "Search evidence is incomplete",
      tone: "watch",
    });
  }
  if (items.length === 0) {
    items.push({
      detail: "No immediate workload, feedback or search-data gaps are visible in this scope.",
      label: "Operational indicators are balanced",
      tone: "good",
    });
  }
  return items;
}

function percent(value: number, total: number) {
  if (total === 0) return 0;
  return Math.min(100, Math.max(0, Math.round((value / total) * 100)));
}
