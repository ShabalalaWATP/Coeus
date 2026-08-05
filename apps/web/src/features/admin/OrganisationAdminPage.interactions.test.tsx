import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import OrganisationAdminPage from "./OrganisationAdminPage";
import { renderWithProviders } from "../../test/test-utils";

const fixtures = vi.hoisted(() => ({
  child: {
    id: "00000000-0000-4000-8000-000000000002",
    name: "Synthetic Child",
    shortName: "Child",
    category: "delivery_team",
    parentId: "00000000-0000-4000-8000-000000000001",
    isActive: true,
    validFrom: "2026-08-03T10:00:00Z",
    validUntil: null,
    timeZone: "Europe/London",
    description: "Synthetic child unit.",
    version: 1,
  },
  target: {
    id: "00000000-0000-4000-8000-000000000003",
    name: "Synthetic Target",
    shortName: "Target",
    category: "branch",
    parentId: "00000000-0000-4000-8000-000000000001",
    isActive: true,
    validFrom: "2026-08-03T10:00:00Z",
    validUntil: null,
    timeZone: "Europe/London",
    description: "Synthetic target unit.",
    version: 3,
  },
}));

type CloseProps = { onClose: () => void };
type TreeProps = {
  onBootstrap: () => void;
  onSelect: (unit: typeof fixtures.child) => void;
};
type InspectorProps = {
  onCreate: () => void;
  onDeactivate: () => void;
  onEdit: () => void;
  onManageAuthority: () => void;
  onManageRoster: () => void;
  onMerge: () => void;
  onReparent: () => void;
  onSplit: () => void;
  unit?: typeof fixtures.child;
};
type ModeProps = CloseProps & { mode?: string; target?: typeof fixtures.target };

function panel(name: string) {
  return ({ onClose }: CloseProps) => (
    <div>
      <h2>{name}</h2>
      <button onClick={onClose} type="button">
        Close {name}
      </button>
    </div>
  );
}

vi.mock("./OrganisationTree", () => ({
  OrganisationTree: ({ onBootstrap, onSelect }: TreeProps) => (
    <div>
      <button onClick={onBootstrap} type="button">
        Bootstrap tree
      </button>
      <button onClick={() => onSelect(fixtures.child)} type="button">
        Select child
      </button>
      <button onClick={() => onSelect(fixtures.target)} type="button">
        Select target
      </button>
    </div>
  ),
}));
vi.mock("./OrganisationCutoverReadinessPanel", () => ({
  OrganisationCutoverReadinessPanel: () => <div>Readiness panel</div>,
}));
vi.mock("./OrganisationCutoverReleasePanel", () => ({
  OrganisationCutoverReleasePanel: () => <div>Release panel</div>,
}));
vi.mock("./OrganisationBootstrapPanel", () => ({
  OrganisationBootstrapPanel: panel("Bootstrap panel"),
}));
vi.mock("./OrganisationAuthorityPanel", () => ({
  OrganisationAuthorityPanel: panel("Authority panel"),
}));
vi.mock("./OrganisationMutationPanel", () => ({
  OrganisationMutationPanel: ({ mode, onClose }: ModeProps) => (
    <div>
      <h2>Mutation {mode}</h2>
      <button onClick={onClose} type="button">
        Close mutation
      </button>
    </div>
  ),
}));
vi.mock("./OrganisationMergePanel", () => ({ OrganisationMergePanel: panel("Merge panel") }));
vi.mock("./OrganisationRosterPanel", () => ({ OrganisationRosterPanel: panel("Roster panel") }));
vi.mock("./OrganisationSplitPanel", () => ({ OrganisationSplitPanel: panel("Split panel") }));
vi.mock("./OrganisationStructurePanel", () => ({
  OrganisationStructurePanel: ({ mode, onClose, target }: ModeProps) => (
    <div>
      <h2>Structure {mode}</h2>
      <p>{target?.shortName ?? "No target"}</p>
      <button onClick={onClose} type="button">
        Close structure
      </button>
    </div>
  ),
}));
vi.mock("./OrganisationUnitInspector", () => ({
  OrganisationUnitInspector: (props: InspectorProps) => (
    <div>
      <h2>{props.unit ? `Inspector ${props.unit.shortName}` : "Empty inspector"}</h2>
      <button onClick={props.onCreate} type="button">
        Create
      </button>
      <button onClick={props.onEdit} type="button">
        Edit
      </button>
      <button onClick={props.onManageAuthority} type="button">
        Authority
      </button>
      <button onClick={props.onManageRoster} type="button">
        Roster
      </button>
      <button onClick={props.onMerge} type="button">
        Merge
      </button>
      <button onClick={props.onSplit} type="button">
        Split
      </button>
      <button onClick={props.onReparent} type="button">
        Move
      </button>
      <button onClick={props.onDeactivate} type="button">
        Deactivate
      </button>
    </div>
  ),
}));

test("moves through every organisation administration panel and returns safely", async () => {
  renderWithProviders(<OrganisationAdminPage />, "/admin/organisation");

  expect(screen.getByRole("heading", { name: "Empty inspector" })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Bootstrap tree" }));
  expect(screen.getByRole("heading", { name: "Bootstrap panel" })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Close Bootstrap panel" }));

  await userEvent.click(screen.getByRole("button", { name: "Select child" }));
  expect(screen.getByRole("heading", { name: "Inspector Child" })).toBeVisible();

  const transitions = [
    ["Create", "Mutation create", "Close mutation"],
    ["Edit", "Mutation edit", "Close mutation"],
    ["Authority", "Authority panel", "Close Authority panel"],
    ["Roster", "Roster panel", "Close Roster panel"],
    ["Merge", "Merge panel", "Close Merge panel"],
    ["Split", "Split panel", "Close Split panel"],
    ["Deactivate", "Structure deactivate", "Close structure"],
  ];
  for (const [action, heading, close] of transitions) {
    await userEvent.click(screen.getByRole("button", { name: action }));
    expect(screen.getByRole("heading", { name: heading })).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: close }));
  }

  await userEvent.click(screen.getByRole("button", { name: "Move" }));
  expect(screen.getByText("Select a new parent")).toBeVisible();
  expect(screen.getByText("Choose the new parent for Child")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Select child" }));
  expect(screen.getByRole("heading", { name: "Inspector Child" })).toBeVisible();

  await userEvent.click(screen.getByRole("button", { name: "Move" }));
  await userEvent.click(screen.getByRole("button", { name: "Select target" }));
  expect(screen.getByRole("heading", { name: "Structure reparent" })).toBeVisible();
  expect(screen.getByText("Target")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Close structure" }));
  expect(screen.getByRole("heading", { name: "Inspector Child" })).toBeVisible();
});
