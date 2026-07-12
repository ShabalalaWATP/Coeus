import { screen } from "@testing-library/react";

import JiocOversightPage from "./JiocOversightPage";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("renders workflow ownership and capacity from the oversight endpoint", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          countsByState: [{ key: "ANALYST_IN_PROGRESS", count: 1 }],
          countsByRoute: [{ key: "rfa", count: 1 }],
          teams: [
            {
              teamId: "team-1",
              name: "Assessment Team",
              kind: "rfa",
              activeMembers: 4,
              availableMembers: 2,
              liveTaskCount: 1,
            },
          ],
          analysts: [
            {
              userId: "analyst-1",
              displayName: "Assessment Analyst",
              teamIds: ["team-1"],
              liveTaskCount: 1,
            },
          ],
          tasks: [
            {
              ticketId: "ticket-1",
              reference: "TCK-0001",
              state: "ANALYST_IN_PROGRESS",
              route: "rfa",
              teamId: "team-1",
              teamName: "Assessment Team",
              analystCount: 2,
              workPackageCount: 3,
              completedWorkPackageCount: 1,
            },
          ],
        }),
    }),
  );

  renderWithProviders(<JiocOversightPage />, "/jioc/oversight");
  expect(await screen.findByRole("heading", { name: "Area teams" })).toBeVisible();
  expect(screen.getByText("TCK-0001")).toBeVisible();
  expect(screen.getByText("Assessment Analyst")).toBeVisible();
  expect(screen.getByText("1 of 3")).toBeVisible();
});

test("offers recovery when oversight cannot be loaded", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: () => Promise.resolve({ error: { code: "unavailable", message: "Unavailable" } }),
    }),
  );
  renderWithProviders(<JiocOversightPage />, "/jioc/oversight");
  expect(await screen.findByRole("button", { name: "Retry" })).toBeVisible();
});

test("shows honest empty workload states", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          countsByState: [],
          countsByRoute: [],
          teams: [],
          analysts: [],
          tasks: [],
        }),
    }),
  );

  renderWithProviders(<JiocOversightPage />, "/jioc/oversight");
  expect(await screen.findByText("No active tasks.")).toBeVisible();
  expect(screen.getByText("No analysts are allocated.")).toBeVisible();
});

test("labels unrouted work and plural analyst workloads", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          countsByState: [],
          countsByRoute: [],
          teams: [],
          analysts: [
            {
              userId: "analyst-1",
              displayName: "Shared Analyst",
              teamIds: ["team-1", "team-2"],
              liveTaskCount: 2,
            },
          ],
          tasks: [
            {
              ticketId: "ticket-1",
              reference: "TCK-UNROUTED",
              state: "JIOC_REVIEW",
              route: null,
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
  expect(await screen.findByText("Unrouted")).toBeVisible();
  expect(screen.getByText("Unassigned")).toBeVisible();
  expect(screen.getByText("2 live tasks")).toBeVisible();
  expect(screen.getByText("2 teams")).toBeVisible();
});
