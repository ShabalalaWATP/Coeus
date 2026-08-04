import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import OrganisationAdminPage from "./OrganisationAdminPage";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const root = {
  id: "00000000-0000-4000-8000-000000000001",
  name: "Synthetic Defence Intelligence",
  shortName: "Synthetic DI",
  category: "command",
  parentId: null,
  isActive: true,
  validFrom: "2026-08-03T10:00:00Z",
  validUntil: null,
  timeZone: "Europe/London",
  description: "Synthetic root used for exercise administration.",
  version: 2,
};

const child = {
  ...root,
  id: "00000000-0000-4000-8000-000000000002",
  name: "Joint User Branch",
  shortName: "Joint User",
  category: "branch",
  parentId: root.id,
  isActive: false,
  description: "",
  version: 1,
};

const readiness = {
  ready: true,
  checks: [{ code: "migration_head", status: "passed", observedCount: 1, requiredCount: 1 }],
};

const emptyRelease = {
  candidateDigest: null,
  manifest: null,
  slices: ["organisation", "calendar", "task_capacity"].map((slice) => ({
    slice,
    status: "not_previewed",
    previewDigest: null,
    proposedByUserId: null,
    approvals: [],
    activatedByUserId: null,
    activatedAt: null,
  })),
  eligible: false,
};

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("explores nested units and shows selected authority without implying operational cutover", async () => {
  const commandBodies: Record<string, unknown>[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (url.endsWith("/cutover-readiness")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(readiness) });
      }
      if (url.endsWith("/cutover-release")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(emptyRelease) });
      }
      if (url.endsWith("/unit-previews")) {
        const body = typeof init?.body === "string" ? init.body : "{}";
        commandBodies.push(JSON.parse(body) as Record<string, unknown>);
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              operation: "create",
              unitId: commandBodies[0].unitId,
              scopeUnitId: root.id,
              expectedVersion: root.version,
              previewHash: "a".repeat(64),
              affectedDescendants: 0,
              affectedMemberships: 0,
              affectedGrants: 0,
              affectedTaskLegs: 0,
            }),
        });
      }
      if (url.endsWith("/unit-commands")) {
        const body = typeof init?.body === "string" ? init.body : "{}";
        commandBodies.push(JSON.parse(body) as Record<string, unknown>);
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              unitId: commandBodies[0].unitId,
              version: 1,
              topologyRevisionId: "00000000-0000-4000-8000-000000000005",
              replayed: false,
            }),
        });
      }
      if (url.includes("parentId=")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ units: [child] }) });
      }
      if (url.includes("/grants")) {
        const selectedChild = url.includes(encodeURIComponent(child.id));
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              grants: selectedChild
                ? []
                : [
                    {
                      id: "00000000-0000-4000-8000-000000000003",
                      managerUserId: "00000000-0000-4000-8000-000000000004",
                      rootUnitId: root.id,
                      action: "organisation:view_aggregate",
                      includeDescendants: true,
                      validFrom: "2026-08-03T10:00:00Z",
                      validUntil: null,
                      revokedAt: null,
                      sourceGrantId: null,
                      delegationDepth: 0,
                      version: 1,
                    },
                    {
                      id: "00000000-0000-4000-8000-000000000006",
                      managerUserId: "00000000-0000-4000-8000-000000000004",
                      rootUnitId: root.id,
                      action: "organisation:create",
                      includeDescendants: true,
                      validFrom: "2026-08-03T10:00:00Z",
                      validUntil: null,
                      revokedAt: null,
                      sourceGrantId: null,
                      delegationDepth: 0,
                      version: 1,
                    },
                  ],
            }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ units: [root] }) });
    }),
  );

  renderWithProviders(<OrganisationAdminPage />, "/admin/organisation");
  expect(await screen.findByText("Synthetic DI")).toBeVisible();
  expect(
    screen.getByText("Select a unit to inspect its details and delegated authority."),
  ).toBeVisible();

  await userEvent.click(screen.getByRole("button", { name: /Synthetic DI Synthetic Defence/ }));
  expect(await screen.findByRole("heading", { name: root.name })).toBeVisible();
  expect(await screen.findByText("view aggregate")).toBeVisible();
  expect(screen.getAllByText("Includes descendants")).toHaveLength(2);
  expect(screen.getByText(/operational routing remain on the current service/i)).toBeVisible();

  await userEvent.click(screen.getByRole("button", { name: "Add child unit" }));
  await userEvent.type(screen.getByLabelText("Name"), "Synthetic Analysis Team");
  await userEvent.type(screen.getByLabelText("Short name"), "Analysis");
  await userEvent.selectOptions(
    await screen.findByLabelText("Authorising grant"),
    "00000000-0000-4000-8000-000000000006",
  );
  await userEvent.type(screen.getByLabelText("Reason"), "Create an exercise delivery team.");
  await userEvent.click(screen.getByRole("button", { name: "Review impact" }));
  expect(await screen.findByText("Impact checked")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Confirm creation" }));
  expect(await screen.findByRole("heading", { name: root.name })).toBeVisible();
  const command = commandBodies[1] as { request: { unitId: string }; previewHash: string };
  expect(command.request.unitId).toBe(commandBodies[0].unitId);
  expect(command.previewHash).toBe("a".repeat(64));

  await userEvent.click(screen.getByRole("button", { name: `Expand ${root.name}` }));
  expect(await screen.findByText("Joint User")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: /Joint User Joint User Branch/ }));
  expect(await screen.findByRole("heading", { name: child.name })).toBeVisible();
  expect(screen.getByText("No description has been recorded.")).toBeVisible();
  expect(await screen.findByText("No grants are rooted at this unit.")).toBeVisible();
  expect(screen.getAllByText("Inactive")).toHaveLength(2);

  await userEvent.click(screen.getByRole("button", { name: `Collapse ${root.name}` }));
  await waitFor(() => expect(screen.queryByText("Joint User")).not.toBeInTheDocument());
});

test("explains an organisation that has not been bootstrapped", async () => {
  let bootstrapBody: Record<string, unknown> | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (url.endsWith("/cutover-readiness")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(readiness) });
      }
      if (url.endsWith("/cutover-release")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(emptyRelease) });
      }
      if (url.endsWith("/bootstrap")) {
        const body = typeof init?.body === "string" ? init.body : "{}";
        const parsedBody = JSON.parse(body) as Record<string, unknown>;
        bootstrapBody = parsedBody;
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              rootUnitId: parsedBody.rootUnitId,
              topologyRevisionId: "00000000-0000-4000-8000-000000000007",
              grantIds: [],
            }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ units: [] }) });
    }),
  );

  renderWithProviders(<OrganisationAdminPage />, "/admin/organisation");

  expect(await screen.findByRole("heading", { name: "No organisation root" })).toBeVisible();
  expect(screen.getByText(/protected bootstrap ceremony/i)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Set up organisation" }));
  await userEvent.type(screen.getByLabelText("Root name"), "Synthetic Root");
  await userEvent.type(screen.getByLabelText("Short name"), "Root");
  await userEvent.type(screen.getByLabelText("Current password"), "current-password");
  await userEvent.type(screen.getByLabelText("Setup code"), "s".repeat(32));
  await userEvent.click(screen.getByRole("button", { name: "Create organisation root" }));
  await waitFor(() =>
    expect(
      screen.queryByRole("heading", { name: "Create the organisation root" }),
    ).not.toBeInTheDocument(),
  );
  expect(bootstrapBody?.rootName).toBe("Synthetic Root");
  expect(bootstrapBody?.currentPassword).toBe("current-password");
  expect(bootstrapBody?.setupNonce).toBe("s".repeat(32));
  expect(screen.queryByDisplayValue("current-password")).not.toBeInTheDocument();
});

test("presents a recoverable management-plane error", async () => {
  let calls = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.endsWith("/cutover-readiness")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(readiness) });
      }
      if (url.endsWith("/cutover-release")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(emptyRelease) });
      }
      calls += 1;
      if (calls <= 2) {
        return Promise.resolve({
          ok: false,
          status: 503,
          json: () => Promise.resolve({ error: { code: "unavailable", message: "Unavailable" } }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ units: [] }) });
    }),
  );

  renderWithProviders(<OrganisationAdminPage />, "/admin/organisation");
  await userEvent.click(await screen.findByRole("button", { name: "Retry" }, { timeout: 4_000 }));

  expect(await screen.findByRole("heading", { name: "No organisation root" })).toBeVisible();
});
