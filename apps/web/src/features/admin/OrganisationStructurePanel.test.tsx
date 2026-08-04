import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { OrganisationStructurePanel } from "./OrganisationStructurePanel";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const unit = {
  id: "00000000-0000-4000-8000-000000000021",
  name: "Synthetic Analysis Team",
  shortName: "Analysis",
  category: "delivery_team" as const,
  parentId: "00000000-0000-4000-8000-000000000020",
  isActive: true,
  validFrom: "2026-08-03T10:00:00Z",
  validUntil: null,
  timeZone: "Europe/London",
  description: "Synthetic team.",
  version: 3,
};

const target = {
  ...unit,
  id: "00000000-0000-4000-8000-000000000022",
  name: "Synthetic Target Branch",
  shortName: "Target",
  category: "branch" as const,
  parentId: "00000000-0000-4000-8000-000000000023",
  version: 5,
};

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("freezes and executes a reviewed reparent command", async () => {
  const requests: Record<string, unknown>[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (url.includes("/grants")) return grantResponse("organisation:reparent");
      const body = typeof init?.body === "string" ? init.body : "{}";
      requests.push(JSON.parse(body) as Record<string, unknown>);
      if (url.endsWith("/reparent-previews")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              unitId: unit.id,
              newParentId: target.id,
              previewHash: "b".repeat(64),
              impact: {
                sourceParentId: unit.parentId,
                sourceTopologyRevisionId: "00000000-0000-4000-8000-000000000024",
                descendants: 2,
                memberships: 4,
                grants: 1,
                capabilityMappings: 0,
                activeTaskLegs: 3,
                reservations: 0,
                teamCalendarEvents: 0,
                pendingTransfers: 0,
                savedViews: 0,
                newlyCoveringGrants: 0,
                maximumResultDepth: 4,
                stateDigest: "state",
              },
            }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            unitId: unit.id,
            parentId: target.id,
            version: 4,
            topologyRevisionId: "00000000-0000-4000-8000-000000000025",
            replayed: false,
          }),
      });
    }),
  );
  const onClose = vi.fn();
  renderWithProviders(
    <OrganisationStructurePanel mode="reparent" onClose={onClose} target={target} unit={unit} />,
    "/admin/organisation",
  );

  await screen.findByRole("option", { name: /Descendant authority/ });
  await userEvent.selectOptions(screen.getByLabelText("Authorising grant"), "grant-id");
  await userEvent.type(screen.getByLabelText("Reason"), "Move the synthetic team.");
  await userEvent.click(screen.getByRole("button", { name: "Review impact" }));
  expect(await screen.findByText(/2 descendants, 4 memberships/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Confirm move" }));

  expect(onClose).toHaveBeenCalledTimes(1);
  const command = requests[1] as { previewHash: string; request: Record<string, unknown> };
  expect(command.previewHash).toBe("b".repeat(64));
  expect(command.request).toEqual(requests[0]);
});

test("blocks deactivation confirmation when the server reports dependencies", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.includes("/grants")) return grantResponse("organisation:restructure");
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            request: {
              unitId: unit.id,
              expectedVersion: unit.version,
              authorisingGrantId: "grant-id",
              reason: "Review deactivation.",
            },
            previewHash: "c".repeat(64),
            impact: {
              activeChildren: 1,
              activeDescendants: 1,
              memberships: 2,
              directGrants: 0,
              deliveryProfiles: 1,
              capabilityMappings: 0,
              activeTaskLegs: 2,
              reservations: 0,
              teamCalendarEvents: 0,
              pendingTransfers: 0,
              savedViews: 0,
              stateDigest: "state",
              blockingCount: 4,
            },
          }),
      });
    }),
  );
  renderWithProviders(
    <OrganisationStructurePanel mode="deactivate" onClose={vi.fn()} unit={unit} />,
    "/admin/organisation",
  );

  await screen.findByRole("option", { name: /Descendant authority/ });
  await userEvent.selectOptions(screen.getByLabelText("Authorising grant"), "grant-id");
  await userEvent.type(screen.getByLabelText("Reason"), "Review deactivation.");
  await userEvent.click(screen.getByRole("button", { name: "Review impact" }));

  expect(await screen.findByText(/4 blocking dependencies/)).toBeVisible();
  expect(screen.getByRole("button", { name: "Confirm deactivation" })).toBeDisabled();
});

test("executes a deactivation after a clean direct-authority preview", async () => {
  const requests: Record<string, unknown>[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (url.includes("/grants")) return grantResponse("organisation:restructure", false);
      const body = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<
        string,
        unknown
      >;
      requests.push(body);
      if (url.endsWith("/deactivation-previews")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              request: body,
              previewHash: "e".repeat(64),
              impact: {
                activeChildren: 0,
                activeDescendants: 0,
                memberships: 0,
                directGrants: 0,
                deliveryProfiles: 0,
                capabilityMappings: 0,
                activeTaskLegs: 0,
                reservations: 0,
                teamCalendarEvents: 0,
                pendingTransfers: 0,
                savedViews: 0,
                stateDigest: "state",
                blockingCount: 0,
              },
            }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            unitId: unit.id,
            version: 4,
            topologyRevisionId: "00000000-0000-4000-8000-000000000026",
            replayed: false,
          }),
      });
    }),
  );
  const onClose = vi.fn();
  renderWithProviders(
    <OrganisationStructurePanel mode="deactivate" onClose={onClose} unit={unit} />,
    "/admin/organisation",
  );

  await screen.findByRole("option", { name: /Direct authority/ });
  await userEvent.selectOptions(screen.getByLabelText("Authorising grant"), "grant-id");
  await userEvent.type(screen.getByLabelText("Reason"), "Retire the synthetic unit.");
  await userEvent.click(screen.getByRole("button", { name: "Review impact" }));
  expect(await screen.findByText(/No blocking dependencies/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Confirm deactivation" }));
  expect(onClose).toHaveBeenCalledTimes(1);
  expect(requests[1]).toMatchObject({ previewHash: "e".repeat(64), request: requests[0] });
});

test("requires a selected parent and explains absent authority", async () => {
  let applicable = true;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.includes("/grants")) {
        return applicable
          ? grantResponse("organisation:reparent")
          : Promise.resolve({ ok: true, json: () => Promise.resolve({ grants: [] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    }),
  );
  const { unmount } = renderWithProviders(
    <OrganisationStructurePanel mode="reparent" onClose={vi.fn()} unit={unit} />,
    "/admin/organisation",
  );
  await screen.findByRole("option", { name: /Descendant authority/ });
  await userEvent.selectOptions(screen.getByLabelText("Authorising grant"), "grant-id");
  await userEvent.type(screen.getByLabelText("Reason"), "Attempt without a target.");
  await userEvent.click(screen.getByRole("button", { name: "Review impact" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Select a new parent unit.");

  unmount();
  resetQueryClientForTests();
  applicable = false;
  renderWithProviders(
    <OrganisationStructurePanel mode="reparent" onClose={vi.fn()} target={target} unit={unit} />,
    "/admin/organisation",
  );
  expect(await screen.findByText(/No active reparent grant/)).toBeVisible();
  expect(screen.getByRole("button", { name: "Review impact" })).toBeDisabled();
});

function grantResponse(action: string, includeDescendants = true) {
  return Promise.resolve({
    ok: true,
    json: () =>
      Promise.resolve({
        grants: [
          {
            id: "grant-id",
            managerUserId: "manager-id",
            rootUnitId: unit.parentId,
            action,
            includeDescendants,
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
