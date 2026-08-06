import { screen } from "@testing-library/react";

import { WorkspaceAssignedWork } from "./WorkspaceAssignedWork";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const unitId = "db452823-66e0-5f20-826f-0e0d4e27cf65";
const analyst = "8f2d2c86-0d0e-4a2c-8b0f-1f5a4b6d9c31";

function board(overrides: Record<string, unknown> = {}) {
  return {
    cards: [
      {
        taskId: "0f6a1f47-3e9c-4e64-9d4f-6f1a4a3d0b21",
        reference: "EXR-2002",
        title: "Assess available evidence",
        column: "in_progress",
        targetDate: "2026-08-08",
        packages: [
          {
            packageId: "7c1c66f2-1a3b-4d7f-9a41-3b2f8f7b6a10",
            title: "Assess available evidence",
            accountableUserId: analyst,
            dueAt: "2026-08-08T00:00:00Z",
            state: "in_progress",
          },
        ],
      },
    ],
    ...overrides,
  };
}

function people() {
  return { items: [{ userId: analyst, displayName: "Lewis Ferguson" }] };
}

function stubFetch(handler: (url: string) => unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const body = handler(url);
      if (body === null) {
        return Promise.resolve({
          ok: false,
          status: 403,
          json: () =>
            Promise.resolve({ error: { code: "forbidden", message: "Not permitted." } }),
        });
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
    }),
  );
}

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("names the analyst against each dated package", async () => {
  stubFetch((url) => (url.includes("/board") ? board() : people()));

  renderWithProviders(<WorkspaceAssignedWork includeDescendants={false} unitId={unitId} />);

  expect(await screen.findByText("Lewis Ferguson")).toBeVisible();
  expect(screen.getByText("Assess available evidence")).toBeVisible();
  expect(screen.getByText("Sat 8 Aug")).toBeVisible();
});

test("falls back to Unassigned when nobody owns the package", async () => {
  stubFetch((url) =>
    url.includes("/board")
      ? board({
          cards: [
            {
              ...board().cards[0],
              packages: [{ ...board().cards[0].packages[0], accountableUserId: null }],
            },
          ],
        })
      : people(),
  );

  renderWithProviders(<WorkspaceAssignedWork includeDescendants={false} unitId={unitId} />);

  expect(await screen.findByText("Unassigned")).toBeVisible();
});

test("follows the descendant scope so a parent unit is not shown as empty", async () => {
  const seen: string[] = [];
  stubFetch((url) => {
    seen.push(url);
    return url.includes("/board") ? board() : people();
  });

  renderWithProviders(<WorkspaceAssignedWork includeDescendants unitId={unitId} />);
  await screen.findByText("Lewis Ferguson");

  expect(seen.filter((url) => url.includes("scope=descendants"))).toHaveLength(2);
});

test("explains an empty board rather than rendering nothing", async () => {
  stubFetch((url) => (url.includes("/board") ? board({ cards: [] }) : people()));

  renderWithProviders(<WorkspaceAssignedWork includeDescendants={false} unitId={unitId} />);

  expect(await screen.findByText("No assigned work is dated in this team.")).toBeVisible();
});

test("keeps the calendar usable when the board is refused", async () => {
  stubFetch((url) => (url.includes("/board") ? null : people()));

  renderWithProviders(<WorkspaceAssignedWork includeDescendants={false} unitId={unitId} />);

  expect(await screen.findByText("Assigned work is unavailable.")).toBeVisible();
});
