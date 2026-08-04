import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";

import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";
import { TeamTaskBoardPanel } from "./TeamTaskBoardPanel";

beforeEach(resetQueryClientForTests);
afterEach(() => vi.restoreAllMocks());

function board(cards: unknown[] = [], truncated = false, nextCursor: string | null = null) {
  return {
    unitId: "unit-1",
    asOf: "2026-08-03T12:00:00Z",
    truncated,
    nextCursor,
    aggregates: [],
    scope: "direct",
    cards,
  };
}

test("groups privacy-minimised cards and can request completed work", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve(
            board(
              [
                {
                  ticketId: "ticket-1",
                  workflowLeg: "rfa",
                  reference: "TCK-001",
                  title: "Synthetic assessment",
                  column: "in_progress",
                  priority: "High",
                  targetDate: "2026-08-21",
                  ticketUpdatedAt: "2026-08-03T11:00:00Z",
                  ticketVersion: 4,
                  ownershipVersion: 2,
                  packages: [],
                },
                {
                  ticketId: "ticket-2",
                  workflowLeg: "qc",
                  reference: "TCK-002",
                  title: "Synthetic completed assessment",
                  column: "completed_recently",
                  priority: "Routine",
                  targetDate: null,
                  ticketUpdatedAt: "2026-08-03T11:30:00Z",
                  ticketVersion: 8,
                  ownershipVersion: 3,
                  packages: [],
                },
              ],
              true,
              "next-page",
            ),
          ),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve(board()),
      }),
  );

  renderWithProviders(<TeamTaskBoardPanel unitId="unit-1" />);

  expect(await screen.findByRole("heading", { name: "In progress" })).toBeVisible();
  expect(screen.getByText("Synthetic assessment")).toBeVisible();
  expect(screen.getByRole("heading", { name: "Completed" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Next page" })).toBeEnabled();
  expect(screen.queryByText(/requester/i)).not.toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("checkbox", { name: "Show completed from the last 30 days" }),
  );
  expect(await screen.findByText("No assigned delivery work matches these filters.")).toBeVisible();
  expect(fetch).toHaveBeenLastCalledWith(
    expect.stringContaining("includeCompleted=true"),
    expect.any(Object),
  );
});

test("shows descendant aggregates without leaking child tickets and offers a table", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve({
          ...board([
            {
              ticketId: "visible-ticket",
              workflowLeg: "rfa",
              reference: "TCK-VISIBLE",
              title: "Visible assessment",
              column: "ready",
              priority: "Routine",
              targetDate: null,
              ticketUpdatedAt: "2026-08-03T11:00:00Z",
              ticketVersion: 1,
              ownershipVersion: 1,
              packages: [],
              unitId: "team-visible",
              unitName: "Visible team",
            },
          ]),
          scope: "descendants",
          aggregates: [
            {
              unitId: "team-restricted",
              unitName: "Restricted team",
              column: "in_progress",
              count: null,
              suppressed: true,
            },
          ],
        }),
    }),
  );
  const view = renderWithProviders(<TeamTaskBoardPanel includeDescendants unitId="root-team" />);

  expect(await screen.findByRole("heading", { name: "Management task board" })).toBeVisible();
  expect(screen.getAllByText("Restricted team")).toHaveLength(2);
  expect(screen.getByText("In progress: Fewer than 5")).toBeVisible();
  expect(screen.queryByText("TCK-HIDDEN")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Table" }));
  expect(screen.getByRole("table", { name: "Visible team work" })).toBeVisible();
  expect(fetch).toHaveBeenCalledWith(
    expect.stringContaining("scope=descendants"),
    expect.anything(),
  );
  expect(await axe(view.container)).toHaveNoViolations();
});

test("offers retry without exposing an authority failure", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ error: { code: "not_found", message: "Not found." } }),
    }),
  );
  renderWithProviders(<TeamTaskBoardPanel unitId="unit-1" />);
  expect(await screen.findByText("The team task board could not be loaded.")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(fetch).toHaveBeenCalledTimes(2);
});

test("reviews and atomically confirms a package capacity plan", async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url =
      typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    if (url.includes("/capacity?")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            status: "ready",
            peopleIncluded: 3,
            physicalMinutes: 7_200,
            assignableMinutes: 6_000,
            reservationMinutes: 600,
          }),
      });
    }
    if (url.endsWith("/previews")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            previewHash: "a".repeat(64),
            packageId: "package-1",
            packageVersion: 1,
            ownershipVersion: 2,
            accountableUserId: "analyst-1",
            plannedPackageVersion: 2,
          }),
      });
    }
    if (url.endsWith("/commands")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            packageId: "package-1",
            packageVersion: 2,
            replayed: false,
            reservation: {
              reservationId: "reservation-1",
              userId: "analyst-1",
              packageId: "package-1",
              startsAt: "2026-08-04T08:00:00Z",
              endsAt: "2026-08-04T12:00:00Z",
              reservedMinutes: 60,
              state: "active",
              version: 1,
            },
          }),
      });
    }
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve(
          board([
            {
              ticketId: "ticket-1",
              workflowLeg: "rfa",
              reference: "TCK-001",
              title: "Synthetic assessment",
              column: "in_progress",
              priority: "High",
              targetDate: "2026-08-21",
              ticketUpdatedAt: "2026-08-03T11:00:00Z",
              ticketVersion: 4,
              ownershipVersion: 2,
              packages: [
                {
                  packageId: "package-1",
                  title: "Assess evidence",
                  state: "in_progress",
                  accountableUserId: "analyst-1",
                  estimatedMinutes: 240,
                  remainingMinutes: 180,
                  dueAt: null,
                  priority: 2,
                  version: 1,
                },
              ],
            },
          ]),
        ),
    });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<TeamTaskBoardPanel planningGrantId="grant-1" unitId="unit-1" />);

  await userEvent.click(await screen.findByRole("button", { name: "Plan work" }));
  expect(screen.getByRole("heading", { name: "Plan Assess evidence" })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Review plan" }));
  expect(
    await screen.findByRole("button", { name: "Confirm plan and reserve capacity" }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Confirm plan and reserve capacity" }));
  expect(await screen.findByRole("button", { name: "Plan work" })).toBeVisible();
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/planning/commands"),
    expect.objectContaining({ method: "POST" }),
  );
});
