import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";

import MyWorkPage from "./MyWorkPage";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(resetQueryClientForTests);
afterEach(() => vi.restoreAllMocks());

function card(id: string, column = "in_progress") {
  return {
    ticketId: `ticket-${id}`,
    workflowLeg: "rfa",
    packageId: `package-${id}`,
    reference: `TCK-${id}`,
    ticketTitle: `Synthetic request ${id}`,
    packageTitle: `Assess reporting ${id}`,
    column,
    priority: 2,
    targetDate: "2026-08-10",
    dueAt: null,
    blockedCode: null,
    reviewAt: null,
    ticketVersion: 1,
    ownershipVersion: 1,
    packageVersion: 1,
  };
}

test("pages canonical work and moves focus to the refreshed result heading", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          cards: [card("001")],
          asOf: "2026-08-03T12:00:00Z",
          nextCursor: "page-two",
        }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          cards: [card("002", "ready")],
          asOf: "2026-08-03T12:01:00Z",
          nextCursor: null,
        }),
    });
  vi.stubGlobal("fetch", fetchMock);
  const view = renderWithProviders(<MyWorkPage />, "/analyst/my-work");

  expect(await screen.findByText("Assess reporting 001")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Next page" }));
  expect(await screen.findByText("Assess reporting 002")).toBeVisible();
  await waitFor(() => expect(screen.getByRole("heading", { name: /My work/ })).toHaveFocus());
  expect(fetchMock).toHaveBeenLastCalledWith(
    expect.stringContaining("cursor=page-two"),
    expect.anything(),
  );
  await userEvent.click(screen.getByRole("button", { name: "Previous page" }));
  expect(await screen.findByText("Assess reporting 001")).toBeVisible();
  expect(await axe(view.container)).toHaveNoViolations();
});

test("filters completed work and provides an accessible table alternative", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          cards: [card("003", "completed")],
          asOf: "2026-08-03T12:00:00Z",
          nextCursor: null,
        }),
    }),
  );
  renderWithProviders(<MyWorkPage />, "/analyst/my-work");
  await screen.findByText("Assess reporting 003");
  await userEvent.selectOptions(screen.getByLabelText("Status"), "completed");
  expect(screen.getByRole("checkbox", { name: /Include work completed/ })).toBeChecked();
  await userEvent.click(screen.getByRole("button", { name: "Table" }));

  expect(screen.getByRole("table", { name: "My work results" })).toBeVisible();
  await waitFor(() =>
    expect(fetch).toHaveBeenLastCalledWith(
      expect.stringMatching(
        /includeCompleted=true.*column=completed|column=completed.*includeCompleted=true/,
      ),
      expect.anything(),
    ),
  );
});

test("dropping completed work clears a completed-only status and explains an empty result", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ cards: [], asOf: "2026-08-03T12:00:00Z", nextCursor: null }),
    }),
  );
  renderWithProviders(<MyWorkPage />, "/analyst/my-work");

  expect(await screen.findByText("No work matches these filters.")).toBeVisible();
  await userEvent.selectOptions(screen.getByLabelText("Status"), "completed");
  const includeCompleted = screen.getByRole("checkbox", { name: /Include work completed/ });
  expect(includeCompleted).toBeChecked();

  // Completed work cannot be listed while completed work is excluded.
  await userEvent.click(includeCompleted);
  expect(includeCompleted).not.toBeChecked();
  expect(screen.getByLabelText("Status")).toHaveValue("");
});

test("offers a bounded retry when the projection is unavailable", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: () => Promise.resolve({ error: { code: "unavailable", message: "No." } }),
    }),
  );
  renderWithProviders(<MyWorkPage />, "/analyst/my-work");
  expect(await screen.findByText("Your work is temporarily unavailable.")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(fetch).toHaveBeenCalledTimes(2);
});
