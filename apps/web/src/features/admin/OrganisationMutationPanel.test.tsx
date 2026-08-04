import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { OrganisationMutationPanel } from "./OrganisationMutationPanel";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const unit = {
  id: "00000000-0000-4000-8000-000000000011",
  name: "Synthetic Analysis Team",
  shortName: "Analysis",
  category: "delivery_team" as const,
  parentId: "00000000-0000-4000-8000-000000000010",
  isActive: true,
  validFrom: "2026-08-03T10:00:00Z",
  validUntil: null,
  timeZone: "Europe/London",
  description: "Original description.",
  version: 4,
};

const grant = {
  id: "00000000-0000-4000-8000-000000000012",
  managerUserId: "preview-user",
  rootUnitId: unit.parentId,
  action: "organisation:edit",
  includeDescendants: false,
  validFrom: "2026-08-03T10:00:00Z",
  validUntil: null,
  revokedAt: null,
  sourceGrantId: null,
  delegationDepth: 0,
  version: 1,
};

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("edits a unit using the exact reviewed mutation", async () => {
  const posts: Record<string, unknown>[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (url.includes("/grants")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              grants: [
                grant,
                { ...grant, id: "revoked", revokedAt: "2026-08-03T11:00:00Z" },
                { ...grant, id: "wrong-action", action: "organisation:create" },
              ],
            }),
        });
      }
      const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
        string,
        unknown
      >;
      posts.push(body);
      if (url.endsWith("/unit-previews")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              operation: "edit",
              unitId: unit.id,
              scopeUnitId: unit.id,
              expectedVersion: unit.version,
              previewHash: "d".repeat(64),
              affectedDescendants: 1,
              affectedMemberships: 2,
              affectedGrants: 3,
              affectedTaskLegs: 4,
            }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            unitId: unit.id,
            version: 5,
            topologyRevisionId: "00000000-0000-4000-8000-000000000013",
            replayed: false,
          }),
      });
    }),
  );
  const onClose = vi.fn();
  renderWithProviders(
    <OrganisationMutationPanel mode="edit" onClose={onClose} unit={unit} />,
    "/admin/organisation",
  );

  expect(await screen.findByRole("heading", { name: "Edit Analysis" })).toBeVisible();
  expect(screen.getByLabelText("Unit type")).toBeDisabled();
  await userEvent.clear(screen.getByLabelText("Name"));
  await userEvent.type(screen.getByLabelText("Name"), "Updated Analysis Team");
  await userEvent.clear(screen.getByLabelText("Short name"));
  await userEvent.type(screen.getByLabelText("Short name"), "Updated");
  await userEvent.clear(screen.getByLabelText("Time zone"));
  await userEvent.type(screen.getByLabelText("Time zone"), "UTC");
  await userEvent.clear(screen.getByLabelText("Description"));
  await userEvent.type(screen.getByLabelText("Description"), "Updated description.");
  await userEvent.selectOptions(screen.getByLabelText("Authorising grant"), grant.id);
  await userEvent.type(screen.getByLabelText("Reason"), "Correct the synthetic record.");
  await userEvent.click(screen.getByRole("button", { name: "Review impact" }));

  expect(await screen.findByText(/1 descendants, 2 memberships, 3 grants/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Confirm changes" }));
  await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  expect(posts[0]).toMatchObject({
    operation: "edit",
    unitId: unit.id,
    parentId: null,
    expectedVersion: 4,
    name: "Updated Analysis Team",
    shortName: "Updated",
    category: "delivery_team",
    timeZone: "UTC",
    description: "Updated description.",
    authorisingGrantId: grant.id,
    reason: "Correct the synthetic record.",
  });
  expect(posts[1]).toMatchObject({ previewHash: "d".repeat(64), request: posts[0] });
});

test("explains missing authority and surfaces a failed preview", async () => {
  let grants = false;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.includes("/grants")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              grants: grants ? [{ ...grant, action: "organisation:create" }] : [],
            }),
        });
      }
      return Promise.resolve({
        ok: false,
        status: 409,
        json: () => Promise.resolve({ error: { code: "conflict", message: "Preview changed" } }),
      });
    }),
  );
  const { unmount } = renderWithProviders(
    <OrganisationMutationPanel mode="create" onClose={vi.fn()} parent={unit} />,
    "/admin/organisation",
  );
  expect(await screen.findByText(/No active create grant/)).toBeVisible();
  expect(screen.getByRole("button", { name: "Review impact" })).toBeDisabled();

  unmount();
  resetQueryClientForTests();
  grants = true;
  renderWithProviders(
    <OrganisationMutationPanel mode="create" onClose={vi.fn()} parent={unit} />,
    "/admin/organisation",
  );
  await screen.findByRole("option", { name: /Direct authority/ });
  await userEvent.type(screen.getByLabelText("Name"), "Synthetic Child");
  await userEvent.type(screen.getByLabelText("Short name"), "Child");
  await userEvent.selectOptions(screen.getByLabelText("Unit type"), "other");
  await userEvent.selectOptions(screen.getByLabelText("Authorising grant"), grant.id);
  await userEvent.type(screen.getByLabelText("Reason"), "Exercise failure path.");
  await userEvent.click(screen.getByRole("button", { name: "Review impact" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Preview changed");
  await userEvent.click(screen.getByRole("button", { name: "Close organisation change" }));
});

test("uses safe defaults when creating a rootless draft without a session", async () => {
  const posts: Record<string, unknown>[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (url.includes("/grants")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              grants: [{ ...grant, action: "organisation:create", includeDescendants: true }],
            }),
        });
      }
      const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
        string,
        unknown
      >;
      posts.push(body);
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve(
            url.endsWith("/unit-previews")
              ? {
                  operation: "create",
                  unitId: body.unitId,
                  scopeUnitId: null,
                  expectedVersion: 1,
                  previewHash: "f".repeat(64),
                  affectedDescendants: 0,
                  affectedMemberships: 0,
                  affectedGrants: 0,
                  affectedTaskLegs: 0,
                }
              : {
                  unitId: (body.request as Record<string, unknown>).unitId,
                  version: 1,
                  topologyRevisionId: "00000000-0000-4000-8000-000000000014",
                  replayed: false,
                },
          ),
      });
    }),
  );
  const onClose = vi.fn();
  renderWithProviders(
    <OrganisationMutationPanel mode="create" onClose={onClose} />,
    "/admin/organisation",
    null,
  );

  await screen.findByRole("option", { name: /Descendant authority/ });
  expect(screen.getByLabelText("Time zone")).toHaveValue("Europe/London");
  await userEvent.type(screen.getByLabelText("Name"), "Synthetic Rootless Draft");
  await userEvent.type(screen.getByLabelText("Short name"), "Draft");
  await userEvent.selectOptions(screen.getByLabelText("Authorising grant"), grant.id);
  await userEvent.type(screen.getByLabelText("Reason"), "Exercise safe defaults.");
  await userEvent.click(screen.getByRole("button", { name: "Review impact" }));
  await userEvent.click(await screen.findByRole("button", { name: "Confirm creation" }));

  await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  expect(posts[0]).toMatchObject({ parentId: null, expectedVersion: 1, timeZone: "Europe/London" });
});
