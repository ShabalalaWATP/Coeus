import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { OrganisationRosterPanel } from "./OrganisationRosterPanel";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const unit = {
  id: "00000000-0000-4000-8000-000000000001",
  name: "Synthetic Analysis Team",
  shortName: "Analysis",
  category: "delivery_team" as const,
  parentId: "00000000-0000-4000-8000-000000000009",
  isActive: true,
  validFrom: "2026-08-03T10:00:00Z",
  validUntil: null,
  timeZone: "Europe/London",
  description: "Synthetic delivery team.",
  version: 2,
};

const userId = "00000000-0000-4000-8000-000000000002";
const grantId = "00000000-0000-4000-8000-000000000003";

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("previews and executes the exact new single-home membership", async () => {
  const posts: { body: Record<string, unknown>; url: string }[] = [];
  mockRosterApi(posts);
  renderWithProviders(<OrganisationRosterPanel onClose={vi.fn()} unit={unit} />);

  await screen.findByText("No current members.");
  await userEvent.click(screen.getByRole("button", { name: /Add member/ }));
  await screen.findByRole("option", { name: "Synthetic Analyst" });
  await userEvent.selectOptions(screen.getByLabelText("Person"), userId);
  await userEvent.selectOptions(screen.getByLabelText("Team role"), "deputy");
  await userEvent.click(screen.getByLabelText("Eligible for task assignment"));
  await userEvent.selectOptions(screen.getByLabelText("Authorising grant"), grantId);
  await userEvent.type(screen.getByLabelText("Reason"), "Post to the synthetic rota.");
  await userEvent.click(screen.getByRole("button", { name: "Review impact" }));

  expect(await screen.findByText("2 active task legs are linked.")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Confirm membership" }));
  expect(await screen.findByText("Roster updated.")).toBeVisible();

  expect(posts).toHaveLength(2);
  const preview = posts[0].body;
  const command = posts[1].body as { previewHash: string; request: Record<string, unknown> };
  expect(preview).toMatchObject({
    assignmentEligible: true,
    authorisingGrantId: grantId,
    expectedVersion: 0,
    operation: "create",
    reason: "Post to the synthetic rota.",
    role: "deputy",
    unitId: unit.id,
    userId,
  });
  expect(command.request).toEqual(preview);
  expect(command.previewHash).toBe("a".repeat(64));
});

test("updates, removes and transfers existing roster members", async () => {
  const posts: { body: Record<string, unknown>; url: string }[] = [];
  const membership = {
    membershipId: "00000000-0000-4000-8000-000000000004",
    userId,
    unitId: unit.id,
    role: "member",
    assignmentEligible: false,
    validFrom: "2026-08-01T09:00:00Z",
    validUntil: null,
    state: "active",
    version: 3,
  };
  mockRosterApi(posts, [
    membership,
    {
      ...membership,
      membershipId: "00000000-0000-4000-8000-000000000005",
      userId: "missing-user",
      role: "coordinator",
      assignmentEligible: true,
    },
  ]);
  const onClose = vi.fn();
  renderWithProviders(<OrganisationRosterPanel onClose={onClose} unit={unit} />);

  expect(await screen.findByText("Synthetic Analyst")).toBeVisible();
  expect(screen.getByText("Unknown user")).toBeVisible();
  expect(screen.getByText("Not assignment eligible")).toBeVisible();
  expect(screen.getByText("Assignment eligible")).toBeVisible();

  await userEvent.click(screen.getAllByRole("button", { name: "Edit" })[0]);
  expect(screen.getByRole("heading", { name: "Update Synthetic Analyst" })).toBeVisible();
  expect(screen.getByLabelText("Person")).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Close roster change" }));

  await userEvent.click(screen.getAllByRole("button", { name: "Remove" })[0]);
  expect(screen.getByRole("heading", { name: "Remove Synthetic Analyst" })).toBeVisible();
  expect(screen.getByLabelText("Team role")).toBeDisabled();
  expect(screen.getByLabelText("Eligible for task assignment")).not.toBeChecked();
  await userEvent.selectOptions(screen.getByLabelText("Authorising grant"), grantId);
  await userEvent.type(screen.getByLabelText("Reason"), "End the synthetic posting.");
  await userEvent.click(screen.getByRole("button", { name: "Review impact" }));
  await userEvent.click(await screen.findByRole("button", { name: "Confirm removal" }));
  expect(await screen.findByText("Roster updated.")).toBeVisible();
  expect(posts.at(-2)?.body).toMatchObject({
    assignmentEligible: false,
    expectedVersion: 3,
    membershipId: membership.membershipId,
    operation: "end",
    userId,
  });

  await userEvent.click(screen.getByRole("button", { name: "Transfer member" }));
  expect(screen.getByRole("heading", { name: "Transfer into Analysis" })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Close transfer" }));
  await userEvent.click(screen.getByRole("button", { name: "Close" }));
  expect(onClose).toHaveBeenCalledTimes(1);
});

test("shows bounded roster loading failures and absent authority", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.includes("/grants")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ grants: [] }) });
      }
      return Promise.resolve({
        ok: false,
        status: 503,
        json: () => Promise.resolve({ error: { code: "unavailable", message: "Unavailable" } }),
      });
    }),
  );
  renderWithProviders(<OrganisationRosterPanel onClose={vi.fn()} unit={unit} />);

  expect(
    await screen.findByText("The roster could not be loaded.", undefined, { timeout: 4_000 }),
  ).toBeVisible();
  expect(screen.getByText("No current members.")).toBeVisible();
  expect(screen.getByText("No roster management grant is available.")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: /Add member/ }));
  expect(screen.getByRole("heading", { name: "Add a team member" })).toBeVisible();
});

function mockRosterApi(
  posts: { body: Record<string, unknown>; url: string }[],
  memberships: Record<string, unknown>[] = [],
) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        const body = JSON.parse(typeof init.body === "string" ? init.body : "{}") as Record<
          string,
          unknown
        >;
        posts.push({ body, url });
        if (url.endsWith("membership-previews")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                previewHash: "a".repeat(64),
                request: body,
                snapshot: {
                  activeTaskLegs: 2,
                  currentMembershipVersion: 0,
                  stateDigest: "b".repeat(64),
                  unitVersion: unit.version,
                },
              }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              membershipId: (body.request as Record<string, unknown>).membershipId,
              replayed: false,
              version: 1,
            }),
        });
      }
      if (url.includes("/memberships")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ memberships }) });
      }
      if (url.endsWith("/admin/users")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              users: [
                {
                  clearanceLevel: 3,
                  displayName: "Synthetic Analyst",
                  id: userId,
                  isActive: true,
                  roles: ["Intelligence Analyst"],
                  username: "analyst@example.test",
                },
              ],
            }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            grants: [
              {
                action: "roster:manage",
                delegationDepth: 0,
                id: grantId,
                includeDescendants: true,
                managerUserId: "preview-user",
                revokedAt: null,
                rootUnitId: unit.parentId,
                sourceGrantId: null,
                validFrom: "2026-08-03T10:00:00Z",
                validUntil: null,
                version: 1,
              },
            ],
          }),
      });
    }),
  );
}
