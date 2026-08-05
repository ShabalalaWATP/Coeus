import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { OrganisationTransferForm } from "./OrganisationTransferForm";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const target = {
  id: "00000000-0000-4000-8000-000000000001",
  name: "Target Analysis Team",
  shortName: "Target",
  category: "delivery_team" as const,
  parentId: null,
  isActive: true,
  validFrom: "2026-08-03T10:00:00Z",
  validUntil: null,
  timeZone: "Europe/London",
  description: "Synthetic target.",
  version: 4,
};

const sourceUnit = { ...target, id: "00000000-0000-4000-8000-000000000002", shortName: "Source" };
const user = {
  clearanceLevel: 3,
  displayName: "Synthetic Analyst",
  id: "00000000-0000-4000-8000-000000000003",
  isActive: true,
  roles: ["Intelligence Analyst"],
  username: "analyst@example.test",
};
const grant = {
  action: "roster:transfer" as const,
  delegationDepth: 0,
  id: "00000000-0000-4000-8000-000000000004",
  includeDescendants: true,
  managerUserId: "preview-user",
  revokedAt: null,
  rootUnitId: target.id,
  sourceGrantId: null,
  validFrom: "2026-08-03T10:00:00Z",
  validUntil: null,
  version: 1,
};
const membership = {
  assignmentEligible: true,
  membershipId: "00000000-0000-4000-8000-000000000005",
  role: "member" as const,
  state: "active" as const,
  unitId: sourceUnit.id,
  userId: user.id,
  validFrom: "2026-07-01T10:00:00Z",
  validUntil: null,
  version: 3,
};

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("reviews and schedules one exact-boundary transfer without cross-posting", async () => {
  const posts: Record<string, unknown>[] = [];
  mockTransferApi(posts);
  renderWithProviders(
    <OrganisationTransferForm grants={[grant]} onClose={vi.fn()} target={target} users={[user]} />,
  );

  await userEvent.selectOptions(screen.getByLabelText("Person"), user.id);
  expect(await screen.findByText("Source")).toBeVisible();
  await userEvent.selectOptions(screen.getByLabelText("New team role"), "coordinator");
  await userEvent.click(screen.getByLabelText("Eligible for task assignment"));
  await userEvent.selectOptions(screen.getByLabelText("Source authority"), grant.id);
  await userEvent.selectOptions(screen.getByLabelText("Target authority"), grant.id);
  await userEvent.type(screen.getByLabelText("Reason"), "Move to the target synthetic rota.");
  await userEvent.click(screen.getByRole("button", { name: "Review transfer" }));
  expect(await screen.findByText(/3 task legs, 1 future events/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Schedule transfer" }));
  expect(await screen.findByText("Transfer scheduled.")).toBeVisible();

  expect(posts).toHaveLength(2);
  const command = posts[1] as { previewHash: string; request: Record<string, unknown> };
  expect(posts[0]).toMatchObject({
    assignmentEligible: true,
    expectedMembershipVersion: membership.version,
    expectedTargetUnitVersion: target.version,
    reason: "Move to the target synthetic rota.",
    sourceMembershipId: membership.membershipId,
    sourceUnitId: sourceUnit.id,
    targetRole: "coordinator",
    targetUnitId: target.id,
    userId: user.id,
  });
  expect(command.request).toEqual(posts[0]);
  expect(command.previewHash).toBe("c".repeat(64));
});

test("explains absent and same-team home memberships", async () => {
  let sameTeam = false;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.includes("/memberships")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              memberships: sameTeam ? [{ ...membership, unitId: target.id }] : [],
            }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve(target) });
    }),
  );
  const directGrant = { ...grant, includeDescendants: false };
  const { unmount } = renderWithProviders(
    <OrganisationTransferForm
      grants={[directGrant]}
      onClose={vi.fn()}
      target={target}
      users={[user, { ...user, id: "inactive-user", isActive: false }]}
    />,
  );
  expect(screen.queryByRole("option", { name: user.displayName })).toBeVisible();
  expect(screen.queryByRole("option", { name: /inactive/i })).not.toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("Person"), user.id);
  expect(await screen.findByText(/no current home team/i)).toBeVisible();
  expect(screen.getAllByRole("option", { name: "Direct scope" })).toHaveLength(2);

  unmount();
  resetQueryClientForTests();
  sameTeam = true;
  renderWithProviders(
    <OrganisationTransferForm grants={[grant]} onClose={vi.fn()} target={target} users={[user]} />,
  );
  await userEvent.selectOptions(screen.getByLabelText("Person"), user.id);
  expect(await screen.findByText(/already in Target/i)).toBeVisible();
  expect(screen.getByRole("button", { name: "Review transfer" })).toBeDisabled();
});

test("reports a failed transfer command without an authenticated session", async () => {
  const fallback = (url: string) => {
    if (url.includes(`/users/${user.id}/memberships`)) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ memberships: [membership] }),
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(sourceUnit) });
  };
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        const body = JSON.parse(typeof init.body === "string" ? init.body : "{}") as Record<
          string,
          unknown
        >;
        return url.endsWith("transfer-previews")
          ? Promise.resolve({
              ok: true,
              json: () =>
                Promise.resolve({
                  impact: {
                    activeTaskLegs: 0,
                    futureTeamEvents: 0,
                    namedWorkItems: 0,
                    reservations: 0,
                    stateDigest: "d".repeat(64),
                  },
                  previewHash: "c".repeat(64),
                  request: body,
                }),
            })
          : Promise.resolve({
              ok: false,
              status: 409,
              json: () => Promise.resolve({ error: { code: "conflict", message: "Changed" } }),
            });
      }
      return fallback(url);
    }),
  );
  renderWithProviders(
    <OrganisationTransferForm grants={[grant]} onClose={vi.fn()} target={target} users={[user]} />,
    "/admin/organisation",
    null,
  );

  await userEvent.selectOptions(screen.getByLabelText("Person"), user.id);
  await screen.findByText("Source");
  await userEvent.selectOptions(screen.getByLabelText("Source authority"), grant.id);
  await userEvent.selectOptions(screen.getByLabelText("Target authority"), grant.id);
  await userEvent.type(screen.getByLabelText("Reason"), "Review the synthetic transfer.");
  await userEvent.click(screen.getByRole("button", { name: "Review transfer" }));
  await userEvent.click(await screen.findByRole("button", { name: "Schedule transfer" }));
  expect(await screen.findByText(/could not be scheduled/i)).toBeVisible();
});

function mockTransferApi(posts: Record<string, unknown>[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        const body = JSON.parse(typeof init.body === "string" ? init.body : "{}") as Record<
          string,
          unknown
        >;
        posts.push(body);
        if (url.endsWith("transfer-previews")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                impact: {
                  activeTaskLegs: 3,
                  futureTeamEvents: 1,
                  namedWorkItems: 2,
                  reservations: 0,
                  stateDigest: "d".repeat(64),
                },
                previewHash: "c".repeat(64),
                request: body,
              }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ commandId: "id", status: "pending" }),
        });
      }
      if (url.includes(`/users/${user.id}/memberships`)) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ memberships: [membership] }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve(sourceUnit) });
    }),
  );
}
