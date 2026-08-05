import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { OrganisationUnitInspector } from "./OrganisationUnitInspector";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const unit = {
  id: "00000000-0000-4000-8000-000000000031",
  name: "Synthetic Delivery Team",
  shortName: "Delivery",
  category: "delivery_team" as const,
  parentId: "00000000-0000-4000-8000-000000000030",
  isActive: true,
  validFrom: "2026-08-03T10:00:00Z",
  validUntil: null,
  timeZone: "Europe/London",
  description: "Synthetic team.",
  version: 2,
};

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("offers every valid unit action and identifies direct revoked authority", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            grants: [
              {
                id: "grant-id",
                managerUserId: "preview-user",
                rootUnitId: unit.id,
                action: "organisation:reparent",
                includeDescendants: false,
                validFrom: "2026-08-03T10:00:00Z",
                validUntil: null,
                revokedAt: "2026-08-03T12:00:00Z",
                sourceGrantId: null,
                delegationDepth: 0,
                version: 2,
              },
            ],
          }),
      }),
    ),
  );
  const actions = {
    onCreate: vi.fn(),
    onDeactivate: vi.fn(),
    onEdit: vi.fn(),
    onManageAuthority: vi.fn(),
    onManageRoster: vi.fn(),
    onMerge: vi.fn(),
    onReparent: vi.fn(),
    onSplit: vi.fn(),
  };
  renderWithProviders(<OrganisationUnitInspector {...actions} unit={unit} />);

  expect(await screen.findByText("This unit only")).toBeVisible();
  expect(screen.getByText("Revoked")).toBeVisible();
  const buttons = [
    ["Add child unit", actions.onCreate],
    ["Edit unit", actions.onEdit],
    ["Manage authority", actions.onManageAuthority],
    ["Manage roster", actions.onManageRoster],
    ["Merge siblings into this unit", actions.onMerge],
    ["Split unit", actions.onSplit],
    ["Move unit", actions.onReparent],
    ["Deactivate", actions.onDeactivate],
  ] as const;
  for (const [name, handler] of buttons) {
    await userEvent.click(screen.getByRole("button", { name }));
    expect(handler).toHaveBeenCalledTimes(1);
  }
});

test("fails closed when delegated authority cannot be loaded", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 503,
        json: () => Promise.resolve({ error: { code: "unavailable", message: "Unavailable" } }),
      }),
    ),
  );
  renderWithProviders(
    <OrganisationUnitInspector
      onCreate={vi.fn()}
      onDeactivate={vi.fn()}
      onEdit={vi.fn()}
      onManageAuthority={vi.fn()}
      onManageRoster={vi.fn()}
      onMerge={vi.fn()}
      onReparent={vi.fn()}
      onSplit={vi.fn()}
      unit={{ ...unit, parentId: null }}
    />,
  );
  expect(
    await screen.findByText("Management grants could not be loaded.", undefined, {
      timeout: 4_000,
    }),
  ).toBeVisible();
  expect(screen.queryByRole("button", { name: "Move unit" })).not.toBeInTheDocument();
});
