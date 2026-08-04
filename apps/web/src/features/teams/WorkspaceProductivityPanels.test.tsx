import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";

import { resetQueryClientForTests } from "../../app/query-client";
import type { AuthSession } from "../../lib/api-client/auth";
import { renderWithProviders } from "../../test/test-utils";
import { PackageTemplatesPanel } from "./PackageTemplatesPanel";
import { SavedBoardViewsPanel } from "./SavedBoardViewsPanel";

const session: AuthSession = {
  csrfToken: "csrf",
  user: {
    id: "user-1",
    username: "manager@example.test",
    displayName: "Synthetic Manager",
    roles: ["RFA_MANAGER"],
    defaultRoute: "/teams",
    passwordResetRequired: false,
    permissions: [],
  },
};

beforeEach(resetQueryClientForTests);
afterEach(() => vi.restoreAllMocks());

test("saved views load on demand and apply only validated filters", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve({
          items: [
            {
              viewId: "view-1",
              ownerUserId: "user-1",
              unitId: "unit-1",
              name: "Blocked work",
              filters: {
                scope: "direct",
                includeCompleted: false,
                columns: ["blocked"],
                unitIds: [],
              },
              version: 1,
              updatedAt: "2026-08-04T08:00:00Z",
            },
          ],
          nextCursor: null,
        }),
    }),
  );
  const onApply = vi.fn();
  const view = renderWithProviders(
    <SavedBoardViewsPanel
      filters={{ scope: "direct", includeCompleted: false, columns: [], unitIds: [] }}
      onApply={onApply}
      unitId="unit-1"
    />,
    "/teams",
    session,
  );

  expect(fetch).not.toHaveBeenCalled();
  await userEvent.click(screen.getByText("Saved board views"));
  await userEvent.click(await screen.findByRole("button", { name: "Blocked work" }));
  expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ columns: ["blocked"] }));
  expect(await axe(view.container)).toHaveNoViolations();
});

test("authorised managers can create a bounded package template", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ items: [], nextCursor: null }),
    })
    .mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve({
          templateId: "template-1",
          unitId: "unit-1",
          ownerUserId: "user-1",
          name: "Assessment",
          packageTitles: ["Research", "Draft"],
          estimatedMinutes: null,
          priority: null,
          version: 1,
          updatedAt: "2026-08-04T08:00:00Z",
        }),
    })
    .mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ items: [], nextCursor: null }),
    });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(
    <PackageTemplatesPanel grant={{ id: "grant-1", version: 3 }} unitId="unit-1" />,
    "/teams",
    session,
  );

  await userEvent.click(screen.getByText("Package templates"));
  await userEvent.type(screen.getByLabelText("Template name"), "Assessment");
  await userEvent.type(
    screen.getByLabelText("Package titles, one per line"),
    "Research{enter}Draft",
  );
  await userEvent.click(screen.getByRole("button", { name: "Create template" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  expect(fetchMock.mock.calls[1]?.[1]).toEqual(
    expect.objectContaining({
      method: "PUT",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
    }),
  );
});

test("saved views can be created and deleted and empty boards are explained", async () => {
  const saved = {
    viewId: "view-1",
    ownerUserId: "user-1",
    unitId: "unit-1",
    name: "Today",
    filters: { scope: "direct" as const, includeCompleted: false, columns: [], unitIds: [] },
    version: 1,
    updatedAt: "2026-08-04T08:00:00Z",
  };
  let items: (typeof saved)[] = [];
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (init?.method === "PUT") items = [saved];
    if (init?.method === "DELETE") items = [];
    return Promise.resolve({
      ok: true,
      status: init?.method === "DELETE" ? 204 : 200,
      json: () =>
        Promise.resolve(init?.method === "PUT" ? saved : { items, nextCursor: null, url }),
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(
    <SavedBoardViewsPanel filters={saved.filters} onApply={vi.fn()} unitId="unit-1" />,
    "/teams",
    session,
  );
  await userEvent.click(screen.getByText("Saved board views"));
  expect(await screen.findByText("No views saved for this board.")).toBeVisible();
  await userEvent.type(screen.getByLabelText("View name"), " Today ");
  await userEvent.click(screen.getByRole("button", { name: "Save current filters" }));
  await waitFor(() => expect(screen.getByLabelText("View name")).toHaveValue(""));
  expect(items).toEqual([saved]);
  await userEvent.click(await screen.findByRole("button", { name: "Delete Today" }));
  await waitFor(() => expect(items).toEqual([]));
});

test("saved-view loading and mutation failures have bounded messages", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  renderWithProviders(
    <SavedBoardViewsPanel
      filters={{ scope: "direct", includeCompleted: false, columns: [], unitIds: [] }}
      onApply={vi.fn()}
      unitId="unit-1"
    />,
    "/teams",
    session,
  );
  await userEvent.click(screen.getByText("Saved board views"));
  expect(await screen.findByText("Saved views are not available.")).toBeVisible();
  await userEvent.type(screen.getByLabelText("View name"), "Today");
  await userEvent.click(screen.getByRole("button", { name: "Save current filters" }));
  expect(await screen.findByText("The saved view could not be changed.")).toBeVisible();
});

test("templates are read-only without a grant and deletion failures are explained", async () => {
  const template = {
    templateId: "template-1",
    unitId: "unit-1",
    ownerUserId: "user-1",
    name: "Assessment",
    packageTitles: ["Research", "Draft"],
    estimatedMinutes: null,
    priority: null,
    version: 1,
    updatedAt: "2026-08-04T08:00:00Z",
  };
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ items: [template], nextCursor: null }),
    }),
  );
  renderWithProviders(<PackageTemplatesPanel unitId="unit-1" />, "/teams", session);
  await userEvent.click(screen.getByText("Package templates"));
  expect(await screen.findByText("Research · Draft")).toBeVisible();
  expect(screen.getByText(/configuration grant is required/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "Delete Assessment" })).not.toBeInTheDocument();
});

test("authorised managers can delete templates", async () => {
  const template = {
    templateId: "template-1",
    unitId: "unit-1",
    ownerUserId: "user-1",
    name: "Assessment",
    packageTitles: ["Research"],
    estimatedMinutes: null,
    priority: null,
    version: 1,
    updatedAt: "2026-08-04T08:00:00Z",
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ items: [template], nextCursor: null }),
    })
    .mockResolvedValueOnce({ ok: true, status: 204 })
    .mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ items: [], nextCursor: null }),
    });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(
    <PackageTemplatesPanel grant={{ id: "grant-1", version: 1 }} unitId="unit-1" />,
    "/teams",
    session,
  );
  await userEvent.click(screen.getByText("Package templates"));
  await userEvent.click(await screen.findByRole("button", { name: "Delete Assessment" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
});

test("template loading and mutation failures are bounded", async () => {
  const fetchMock = vi
    .fn()
    .mockRejectedValueOnce(new Error("offline"))
    .mockRejectedValue(new Error("write failed"));
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(
    <PackageTemplatesPanel grant={{ id: "grant-1", version: 1 }} unitId="unit-1" />,
    "/teams",
    session,
  );
  await userEvent.click(screen.getByText("Package templates"));
  expect(await screen.findByText("Templates are not available.")).toBeVisible();
  await userEvent.type(screen.getByLabelText("Template name"), "Assessment");
  await userEvent.type(screen.getByLabelText("Package titles, one per line"), "Research");
  await userEvent.click(screen.getByRole("button", { name: "Create template" }));
  expect(await screen.findByText("The template could not be changed.")).toBeVisible();
});
