import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { OrganisationAuthorityPanel } from "./OrganisationAuthorityPanel";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const unit = {
  id: "00000000-0000-4000-8000-000000000001",
  name: "Synthetic Defence Intelligence",
  shortName: "Synthetic DI",
  category: "command" as const,
  parentId: null,
  isActive: true,
  validFrom: "2026-08-03T10:00:00Z",
  validUntil: null,
  timeZone: "Europe/London",
  description: "Synthetic root.",
  version: 2,
};

const source = {
  id: "00000000-0000-4000-8000-000000000002",
  managerUserId: "preview-user",
  rootUnitId: unit.id,
  action: "task:assign" as const,
  includeDescendants: true,
  validFrom: "2026-08-03T10:00:00Z",
  validUntil: null,
  revokedAt: null,
  sourceGrantId: null,
  delegationDepth: 0,
  version: 3,
};

const delegated = {
  ...source,
  id: "00000000-0000-4000-8000-000000000003",
  managerUserId: "00000000-0000-4000-8000-000000000004",
  includeDescendants: false,
  sourceGrantId: source.id,
  delegationDepth: 1,
  version: 2,
};

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("delegates the exact action and bounded scope held by the signed-in manager", async () => {
  const posts: { body: Record<string, unknown>; url: string }[] = [];
  mockAuthorityApi(posts);
  renderWithProviders(<OrganisationAuthorityPanel onClose={vi.fn()} unit={unit} />);

  await screen.findByRole("option", { name: "Synthetic Manager" });
  await userEvent.selectOptions(screen.getByLabelText("Manager"), delegated.managerUserId);
  await userEvent.selectOptions(screen.getByLabelText("Authorising grant"), source.id);
  await userEvent.click(screen.getByLabelText("Include descendant units"));
  await userEvent.type(screen.getByLabelText("Reason"), "Cover the synthetic tasking rota.");
  await userEvent.click(screen.getByRole("button", { name: "Grant authority" }));

  await screen.findByText("Management authority granted.");
  expect(posts).toHaveLength(1);
  expect(posts[0].url).toContain("/admin/organisation/grants");
  expect(posts[0].body).toMatchObject({
    action: "task:assign",
    expectedSourceVersion: 3,
    includeDescendants: true,
    managerUserId: delegated.managerUserId,
    reason: "Cover the synthetic tasking rota.",
    rootUnitId: unit.id,
    sourceGrantId: source.id,
  });
  expect(posts[0].body.commandId).toEqual(expect.any(String));
  expect(posts[0].body.grantId).toEqual(expect.any(String));
});

test("revokes a current grant with its exact version and a recorded reason", async () => {
  const posts: { body: Record<string, unknown>; url: string }[] = [];
  mockAuthorityApi(posts);
  renderWithProviders(<OrganisationAuthorityPanel onClose={vi.fn()} unit={unit} />);

  const items = await screen.findAllByRole("listitem");
  const managerItem = items.find((item) => within(item).queryByText("Synthetic Manager"));
  expect(managerItem).toBeDefined();
  await userEvent.click(within(managerItem!).getByRole("button", { name: "Revoke" }));
  expect(screen.getByText(/Existing work is not reassigned/)).toBeVisible();
  await userEvent.type(screen.getByLabelText("Reason"), "Manager has left the synthetic unit.");
  await userEvent.click(screen.getByRole("button", { name: "Confirm revocation" }));

  await screen.findByText("Management authority revoked.");
  expect(posts).toHaveLength(1);
  expect(posts[0].url).toContain(`/grants/${delegated.id}/revoke`);
  expect(posts[0].body).toMatchObject({
    expectedVersion: delegated.version,
    reason: "Manager has left the synthetic unit.",
  });
});

function mockAuthorityApi(posts: { body: Record<string, unknown>; url: string }[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        posts.push({
          body: JSON.parse(typeof init.body === "string" ? init.body : "{}") as Record<
            string,
            unknown
          >,
          url,
        });
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ grantId: delegated.id, replayed: false, version: 3 }),
        });
      }
      if (url.endsWith("/admin/users")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              users: [
                {
                  clearanceLevel: 3,
                  displayName: "Synthetic Manager",
                  id: delegated.managerUserId,
                  isActive: true,
                  roles: ["Manager"],
                  username: "manager@example.test",
                },
              ],
            }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ grants: [source, delegated] }),
      });
    }),
  );
}
