import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { MyWorkSnapshot } from "./MyWorkSnapshot";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("shows current canonical packages and links to their task", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          cards: [
            {
              ticketId: "ticket/1",
              packageId: "package-1",
              reference: "TCK-001",
              ticketTitle: "Synthetic request",
              packageTitle: "Assess source reporting",
              column: "in_progress",
              dueAt: "2026-08-09T12:00:00Z",
              reviewAt: null,
              targetDate: null,
            },
            {
              ticketId: "ticket-2",
              packageId: "package-2",
              reference: "TCK-002",
              ticketTitle: "No deadline request",
              packageTitle: "Prepare chronology",
              column: "ready",
              dueAt: null,
              reviewAt: null,
              targetDate: null,
            },
            {
              ticketId: "ticket-3",
              packageId: "package-3",
              reference: "TCK-003",
              ticketTitle: "Malformed date request",
              packageTitle: "Check references",
              column: "review",
              dueAt: "not-a-date",
              reviewAt: null,
              targetDate: null,
            },
          ],
          nextCursor: null,
        }),
    }),
  );

  renderWithProviders(<MyWorkSnapshot />);

  expect(await screen.findByText("Assess source reporting")).toBeVisible();
  expect(screen.getByText("In progress")).toBeVisible();
  expect(screen.getByText("No target date")).toBeVisible();
  expect(screen.getByText("Target date unavailable")).toBeVisible();
  expect(screen.getByRole("link", { name: /Assess source reporting/ })).toHaveAttribute(
    "href",
    "/analyst/tasks/ticket%2F1",
  );
  expect(screen.getByRole("link", { name: "View all my work" })).toHaveAttribute(
    "href",
    "/analyst/my-work",
  );
});

test("shows empty work after retrying a bounded failure", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: false,
      status: 503,
      json: () => Promise.resolve({ error: { code: "unavailable", message: "No." } }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ cards: [], nextCursor: null }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<MyWorkSnapshot />);
  expect(await screen.findByRole("alert")).toHaveTextContent("temporarily unavailable");
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByText("You have no active work packages.")).toBeVisible();
});
