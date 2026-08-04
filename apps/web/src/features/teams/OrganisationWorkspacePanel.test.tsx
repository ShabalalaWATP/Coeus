import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";

import { OrganisationWorkspacePanel } from "./OrganisationWorkspacePanel";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const workspaces = {
  asOf: "2026-08-03T12:00:00Z",
  truncated: false,
  workspaces: [
    {
      unit: {
        id: "home-unit",
        name: "Synthetic Home Team",
        shortName: "HOME",
        category: "delivery_team",
      },
      relationship: "home",
      managed: true,
      includeDescendants: false,
      canViewAvailability: true,
      canViewDetail: false,
      canViewTasks: true,
      planningGrantId: null,
      canViewPeople: true,
      canViewCapabilities: true,
      canConfigure: false,
    },
    {
      unit: {
        id: "managed-unit",
        name: "Synthetic Managed Command",
        shortName: "MANAGED",
        category: "command",
      },
      relationship: "managed",
      managed: true,
      includeDescendants: true,
      canViewAvailability: true,
      canViewDetail: true,
      canViewTasks: true,
      planningGrantId: null,
      canViewPeople: true,
      canViewCapabilities: true,
      canConfigure: false,
    },
  ],
};

beforeEach(resetQueryClientForTests);
afterEach(() => vi.restoreAllMocks());

function response(payload: unknown, status = 200) {
  return Promise.resolve({
    ok: status < 400,
    status,
    json: () => Promise.resolve(payload),
  });
}

const metric = {
  key: "headcount",
  label: "Headcount",
  value: 8,
  display: "8",
  scope: "direct",
  period: "current",
};

const overviewPayload = {
  unitId: "home-unit",
  scope: "direct",
  generatedAt: "2026-08-03T12:00:00Z",
  freshUntil: "2026-08-03T12:15:00Z",
  metrics: [metric],
  truncatedCount: 0,
  suppressed: false,
};

const calendarPayload = {
  rootUnitId: "managed-unit",
  scope: "direct",
  generatedAt: "2026-08-03T12:00:00Z",
  unitIds: ["managed-unit"],
  memberCount: 8,
  suppressed: false,
  truncated: false,
  entries: [],
  aggregates: [],
};

test("separates scopes and provides keyboard-operated accessible workspace tabs", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.endsWith("/api/v1/organisation/workspaces")) return response(workspaces);
      if (url.includes("/overview")) return response(overviewPayload);
      if (url.includes("/analytics")) {
        return response({ ...overviewPayload, privacyNotice: "Small cohorts are suppressed." });
      }
      if (url.includes("/people") || url.includes("/capabilities") || url.includes("/search")) {
        return response({ items: [], truncated: false, nextCursor: null });
      }
      return response(calendarPayload);
    }),
  );

  const view = renderWithProviders(<OrganisationWorkspacePanel />);

  expect(await screen.findByRole("heading", { name: "Organisation workspace" })).toBeVisible();
  expect(screen.getAllByText("My team")).toHaveLength(2);
  expect(screen.getByText("Managed teams")).toBeVisible();
  expect(screen.getByRole("heading", { name: "Synthetic Home Team" })).toBeVisible();
  const overview = screen.getByRole("tab", { name: "Overview" });
  overview.focus();
  await userEvent.keyboard("{ArrowRight}{ArrowRight}");
  expect(screen.getByRole("tab", { name: "Calendar" })).toHaveFocus();
  expect(screen.getByRole("tabpanel", { name: "Calendar" })).toBeVisible();
  // The calendar is collapsed until asked for, so its controls only prove an
  // authority boundary once it is open.
  await userEvent.click(screen.getByRole("button", { name: "Open team calendar" }));
  expect(screen.queryByLabelText("Include child units")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Request detailed view" })).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: /Synthetic Managed Command/ }));
  expect(screen.getByRole("heading", { name: "Synthetic Managed Command" })).toBeVisible();
  expect(screen.getByText("Includes child teams")).toBeVisible();
  await userEvent.click(screen.getByRole("tab", { name: "Calendar" }));
  expect(screen.getByLabelText("Include child units")).toBeVisible();
  expect(screen.getByRole("button", { name: "Request detailed view" })).toBeVisible();
  await userEvent.keyboard("{End}");
  expect(screen.getByRole("tab", { name: "Capabilities" })).toHaveFocus();
  await userEvent.keyboard("{Home}");
  expect(screen.getByRole("tab", { name: "Overview" })).toHaveFocus();
  expect(await axe(view.container)).toHaveNoViolations();
});

test("each authorised tab renders its own panel for the selected workspace", async () => {
  const configurable = {
    ...workspaces,
    workspaces: [
      {
        ...workspaces.workspaces[0],
        canConfigure: true,
        configurationGrantId: "grant-1",
        configurationGrantVersion: 2,
      },
    ],
  };
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.endsWith("/api/v1/organisation/workspaces")) return response(configurable);
      if (url.includes("/overview")) return response(overviewPayload);
      if (url.includes("/analytics")) {
        return response({ ...overviewPayload, privacyNotice: "Small cohorts are suppressed." });
      }
      if (url.includes("/policy")) {
        return response({
          unitId: "home-unit",
          wipLimit: 8,
          serviceTargetHours: 72,
          planningCadence: "weekly",
          planningWeekday: 0,
          planningLocalTime: "09:00:00",
          planningDurationMinutes: 60,
          version: 1,
          deliveryPolicyVersion: 1,
          updatedAt: "2026-08-03T12:00:00Z",
        });
      }
      if (url.includes("/people")) return response({ items: [], truncated: false });
      if (url.includes("/capabilities")) return response({ items: [] });
      if (url.includes("/board")) {
        return response({
          unitId: "home-unit",
          asOf: "2026-08-03T12:00:00Z",
          truncated: false,
          nextCursor: null,
          aggregates: [],
          scope: "direct",
          cards: [],
        });
      }
      return response({ items: [], truncated: false, nextCursor: null });
    }),
  );

  renderWithProviders(<OrganisationWorkspacePanel />);

  expect(await screen.findByRole("heading", { name: "Operational overview" })).toBeVisible();
  await userEvent.click(screen.getByRole("tab", { name: "Board" }));
  expect(await screen.findByRole("heading", { name: "Team task board" })).toBeVisible();
  await userEvent.click(screen.getByRole("tab", { name: "People" }));
  expect(await screen.findByRole("heading", { name: "People" })).toBeVisible();
  await userEvent.click(screen.getByRole("tab", { name: "Capabilities" }));
  expect(await screen.findByRole("heading", { name: "Capabilities" })).toBeVisible();
  await userEvent.click(screen.getByRole("tab", { name: "Settings" }));
  expect(await screen.findByRole("heading", { name: "Settings" })).toBeVisible();
});

test("quietly leaves the legacy workspace in place when hierarchy is disabled", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      response(
        {
          error: {
            code: "organisation_management_unavailable",
            message: "Organisation management is not enabled.",
          },
        },
        503,
      ),
    ),
  );

  renderWithProviders(<OrganisationWorkspacePanel />);

  await waitFor(() =>
    expect(screen.queryByLabelText("Loading your organisation workspace")).not.toBeInTheDocument(),
  );
  expect(screen.queryByRole("heading", { name: "Organisation workspace" })).not.toBeInTheDocument();
});

test("shows bounded managed-only scope without implying calendar access", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      response({
        ...workspaces,
        truncated: true,
        workspaces: [
          {
            ...workspaces.workspaces[1],
            managed: false,
            canViewAvailability: false,
            canViewDetail: false,
            canViewTasks: false,
            canViewPeople: false,
            canViewCapabilities: false,
            canConfigure: false,
            planningGrantId: null,
            includeDescendants: false,
          },
        ],
      }),
    ),
  );

  renderWithProviders(<OrganisationWorkspacePanel />);

  expect(await screen.findByText("Managed scope")).toBeVisible();
  expect(screen.queryByText("My team")).not.toBeInTheDocument();
  expect(
    screen.getByText("Workspace views are not included in your authority for this team."),
  ).toBeVisible();
  expect(screen.getByText(/Only the first 100 authorised workspaces/)).toBeVisible();
});

test("offers a bounded retry for unexpected discovery failures", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => response({ error: { code: "server_error", message: "Failed." } }, 500)),
  );

  renderWithProviders(<OrganisationWorkspacePanel />);

  expect(await screen.findByText("Your organisation workspace could not be loaded.")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(fetch).toHaveBeenCalledTimes(2);
});
