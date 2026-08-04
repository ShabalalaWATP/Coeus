import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";
import type { TeamTaskCard, TeamTaskPackage } from "../../lib/api-client/team-task-board";
import { WorkPackagePlanningForm } from "./WorkPackagePlanningForm";

beforeEach(resetQueryClientForTests);
afterEach(() => vi.restoreAllMocks());

const packageItem: TeamTaskPackage = {
  packageId: "package-1",
  title: "Assess evidence",
  state: "ready",
  accountableUserId: "analyst-1",
  estimatedMinutes: null,
  remainingMinutes: null,
  dueAt: "2026-08-20T17:00:00Z",
  priority: null,
  version: 1,
};

const card: TeamTaskCard = {
  ticketId: "ticket-1",
  workflowLeg: "rfa",
  reference: "TCK-001",
  title: "Synthetic assessment",
  column: "in_progress",
  priority: "Routine",
  targetDate: null,
  ticketUpdatedAt: "2026-08-03T11:00:00Z",
  ticketVersion: 2,
  ownershipVersion: 3,
  packages: [packageItem],
};

function form(session: Parameters<typeof renderWithProviders>[2] = undefined) {
  return renderWithProviders(
    <WorkPackagePlanningForm
      card={card}
      onClose={vi.fn()}
      packageItem={packageItem}
      planningGrantId="grant-1"
      unitId="unit-1"
    />,
    "/teams",
    session,
  );
}

test("edits every planning field and reports a rejected preview safely", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: () => Promise.resolve({ error: { code: "conflict", message: "Hidden detail" } }),
    }),
  );
  form();
  for (const [label, value] of [
    ["Estimated hours", "6"],
    ["Remaining hours", "5"],
    ["Reserve now (hours)", "2"],
  ]) {
    const input = screen.getByRole("spinbutton", { name: label });
    await userEvent.clear(input);
    await userEvent.type(input, value);
  }
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Priority" }), "4");
  await userEvent.type(screen.getByRole("textbox", { name: "Priority reason" }), "Urgent.");
  const dates = screen.getAllByDisplayValue(/T/);
  await userEvent.clear(dates[0]);
  await userEvent.type(dates[0], "2026-08-18T09:00");
  await userEvent.click(screen.getByRole("button", { name: "Review plan" }));
  expect(
    await screen.findByText("The plan could not be saved. Refresh the board and try again."),
  ).toBeVisible();
});

test("keeps the visible action disabled and safely omits a missing session token", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url =
        typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve(
            url.endsWith("/previews")
              ? {
                  previewHash: "a".repeat(64),
                  packageId: "package-1",
                  packageVersion: 1,
                  ownershipVersion: 3,
                  accountableUserId: "analyst-1",
                  plannedPackageVersion: 2,
                }
              : {
                  packageId: "package-1",
                  packageVersion: 2,
                  replayed: false,
                  reservation: {},
                },
          ),
      });
    }),
  );
  form(null);
  const review = screen.getByRole("button", { name: "Review plan" });
  expect(review).toBeDisabled();
  fireEvent.submit(review.closest("form")!);
  await userEvent.click(
    await screen.findByRole("button", { name: "Confirm plan and reserve capacity" }),
  );
  expect(JSON.stringify(vi.mocked(fetch).mock.calls)).toContain('"X-CSRF-Token":""');
});
