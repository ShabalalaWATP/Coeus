import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

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

function boardCard(overrides: Record<string, unknown> = {}) {
  return {
    ticketId: "ticket-1",
    workflowLeg: "rfa",
    reference: "TCK-001",
    title: "Synthetic assessment",
    column: "ready",
    priority: "High",
    targetDate: "2026-08-21",
    ticketUpdatedAt: "2026-08-03T11:00:00Z",
    ticketVersion: 4,
    ownershipVersion: 2,
    packages: [],
    ...overrides,
  };
}
test("every board filter narrows the request and clearing restores the default page", async () => {
  const fetchMock = vi.fn((url: string) => {
    if (url.includes("/saved-board-views")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ items: [], nextCursor: null }),
      });
    }
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve(board([boardCard()], false, "page-2")),
    });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<TeamTaskBoardPanel unitId="unit-1" />);

  expect(await screen.findByRole("heading", { name: "Team task board" })).toBeVisible();
  await userEvent.selectOptions(screen.getByLabelText("Status"), "blocked");
  await userEvent.type(screen.getByLabelText("Priority"), "High");
  await userEvent.type(screen.getByLabelText("Due from"), "2026-08-01");
  await userEvent.type(screen.getByLabelText("Due to"), "2026-08-31");

  const boardUrls = () =>
    fetchMock.mock.calls.map(([url]) => url).filter((url) => url.includes("/board?"));
  // Each keystroke refetches, so the fully narrowed request is what matters.
  await waitFor(() => expect(boardUrls().join("\n")).toContain("dueTo=2026-08-31"));
  const narrowed = boardUrls().join("\n");
  expect(narrowed).toContain("column=blocked");
  expect(narrowed).toContain("priority=High");
  expect(narrowed).toContain("dueFrom=2026-08-01");

  await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(screen.getByLabelText("Priority")).toHaveValue("");
  expect(screen.getByLabelText("Status")).toHaveValue("");
  expect(screen.getByLabelText("Due from")).toHaveValue("");
  expect(screen.getByLabelText("Due to")).toHaveValue("");
});

test("paging walks forward and back and returns focus to the board heading", async () => {
  const fetchMock = vi.fn((url: string) => {
    if (url.includes("/saved-board-views")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ items: [], nextCursor: null }),
      });
    }
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve(
          board(
            [boardCard({ ticketId: url.includes("cursor=") ? "ticket-2" : "ticket-1" })],
            false,
            "page-2",
          ),
        ),
    });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<TeamTaskBoardPanel unitId="unit-1" />);

  expect(await screen.findByText("Page 1")).toBeVisible();
  expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Next page" }));

  expect(await screen.findByText("Page 2")).toBeVisible();
  await waitFor(() =>
    expect(screen.getByRole("heading", { name: "Team task board" })).toHaveFocus(),
  );
  expect(fetchMock.mock.calls.some(([url]) => url.includes("cursor=page-2"))).toBe(true);

  await userEvent.click(screen.getByRole("button", { name: "Previous page" }));
  expect(await screen.findByText("Page 1")).toBeVisible();
});

test("a package opens and closes its Intelligence Store links in place", async () => {
  const fetchMock = vi.fn((url: string) => {
    if (url.includes("/store-links")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ items: [], nextCursor: null }),
      });
    }
    if (url.includes("/saved-board-views")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ items: [], nextCursor: null }),
      });
    }
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve(
          board([
            boardCard({
              packages: [
                {
                  packageId: "package-1",
                  title: "Assess evidence",
                  state: "ready",
                  accountableUserId: "user-1",
                  dueAt: null,
                  priority: 1,
                  version: 1,
                },
              ],
            }),
          ]),
        ),
    });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<TeamTaskBoardPanel unitId="unit-1" />);

  await userEvent.click(await screen.findByRole("button", { name: "Store links" }));
  expect(await screen.findByRole("heading", { name: "Intelligence Store links" })).toBeVisible();
  expect(await screen.findByText("No currently authorised Store items are linked.")).toBeVisible();

  await userEvent.click(screen.getByRole("button", { name: "Close Intelligence Store links" }));
  expect(
    screen.queryByRole("heading", { name: "Intelligence Store links" }),
  ).not.toBeInTheDocument();
});

test("applying a saved view replaces every filter and resets paging", async () => {
  const savedView = {
    viewId: "view-1",
    unitId: "unit-1",
    name: "Blocked regional",
    version: 1,
    filters: {
      scope: "descendants",
      includeCompleted: true,
      columns: ["blocked"],
      unitIds: ["team-visible"],
      priority: "Urgent",
      dueFrom: "2026-08-05",
      dueTo: "2026-08-12",
    },
  };
  const fetchMock = vi.fn((url: string) => {
    if (url.includes("/saved-board-views")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ items: [savedView], nextCursor: null }),
      });
    }
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve(
          board([boardCard({ unitId: "team-visible", unitName: "Visible team" })], false, null),
        ),
    });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<TeamTaskBoardPanel includeDescendants unitId="unit-1" />);

  // Saved views load only once the disclosure is opened.
  await userEvent.click(await screen.findByText("Saved board views"));
  await userEvent.click(await screen.findByRole("button", { name: "Blocked regional" }));

  expect(screen.getByLabelText("Status")).toHaveValue("blocked");
  expect(screen.getByLabelText("Priority")).toHaveValue("Urgent");
  expect(screen.getByLabelText("Due from")).toHaveValue("2026-08-05");
  expect(screen.getByLabelText("Due to")).toHaveValue("2026-08-12");
  expect(screen.getByLabelText("Team")).toHaveValue("team-visible");
  expect(
    screen.getByRole("checkbox", { name: "Show completed from the last 30 days" }),
  ).toBeChecked();
});
