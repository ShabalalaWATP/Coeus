import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import JiocOversightPage from "./JiocOversightPage";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("includes re-analysis adjudication in attention work and links to the queue", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          countsByState: [],
          countsByRoute: [],
          countsByAgentDisposition: [],
          teams: [],
          analysts: [],
          tasks: [
            {
              ticketId: "ticket-dispute",
              reference: "TCK-DISPUTE",
              state: "JIOC_REANALYSIS_ADJUDICATION",
              updatedAt: "2026-07-23T09:00:00Z",
              route: "rfa",
              teamId: null,
              teamName: null,
              analystCount: 1,
              workPackageCount: 1,
              completedWorkPackageCount: 1,
            },
          ],
        }),
    }),
  );

  renderWithProviders(<JiocOversightPage />, "/jioc/oversight");

  expect(await screen.findByRole("link", { name: "TCK-DISPUTE" })).toHaveAttribute(
    "href",
    "/jioc/queue?ticket=ticket-dispute",
  );
});

test("filters Agent-routed and held work explicitly", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          countsByState: [],
          countsByRoute: [],
          countsByAgentDisposition: [],
          teams: [],
          analysts: [],
          tasks: [
            {
              ticketId: "agent-routed",
              reference: "TCK-AUTO",
              state: "ANALYST_ASSIGNMENT",
              updatedAt: "2026-07-23T09:00:00Z",
              route: "rfa",
              teamId: null,
              teamName: null,
              analystCount: 0,
              workPackageCount: 0,
              completedWorkPackageCount: 0,
              agentDisposition: "auto_applied",
              agentRoute: "rfa",
              agentRationaleCodes: [],
              agentPolicyVersion: "jioc-routing-policy-v2",
            },
            {
              ticketId: "held",
              reference: "TCK-HELD-FILTER",
              state: "JIOC_INTERVENTION_HOLD",
              updatedAt: "2026-07-23T09:01:00Z",
              route: "cm",
              teamId: null,
              teamName: null,
              analystCount: 0,
              workPackageCount: 0,
              completedWorkPackageCount: 0,
            },
          ],
        }),
    }),
  );

  renderWithProviders(<JiocOversightPage />, "/jioc/oversight");
  const filter = await screen.findByRole("combobox", { name: "Filter oversight tasks" });
  await userEvent.selectOptions(filter, "agent_routed");
  expect(screen.getByText("TCK-AUTO")).toBeVisible();
  expect(screen.queryByText("TCK-HELD-FILTER")).not.toBeInTheDocument();

  await userEvent.selectOptions(filter, "on_hold");
  expect(screen.getByText("TCK-HELD-FILTER")).toBeVisible();
  expect(screen.queryByText("TCK-AUTO")).not.toBeInTheDocument();
});
