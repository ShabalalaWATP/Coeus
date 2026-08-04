import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { OrganisationMergePanel } from "./OrganisationMergePanel";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const parentId = "00000000-0000-4000-8000-000000000009";
const successor = unit("1", "Successor", 5);
const sourceOne = unit("2", "Source One", 2);
const sourceTwo = unit("3", "Source Two", 3);
const grantId = "00000000-0000-4000-8000-000000000004";
const records = [
  record("child_unit", "11"),
  record("membership", "12"),
  record("grant", "13"),
  record("delivery_profile", "14"),
  record("capability", "15"),
  record("task", "16"),
  record("pending_transfer", "17"),
];

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("assesses every dependency and executes the exact reviewed merge plan", async () => {
  const posts: { body: Record<string, unknown>; url: string }[] = [];
  mockMergeApi(posts);
  renderWithProviders(<OrganisationMergePanel onClose={vi.fn()} successor={successor} />);

  await userEvent.click(await screen.findByLabelText(sourceOne.shortName));
  await userEvent.click(screen.getByLabelText(sourceTwo.shortName));
  await userEvent.selectOptions(screen.getByLabelText("Authorising grant"), grantId);
  await userEvent.type(screen.getByLabelText("Reason"), "Consolidate synthetic delivery teams.");
  await userEvent.click(screen.getByRole("button", { name: "Assess dependencies" }));
  expect(await screen.findByText(/7 records require an explicit outcome/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Review merge plan" }));
  expect(await screen.findByText("Plan checked")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Confirm merge" }));
  expect(await screen.findByText("Units merged successfully.")).toBeVisible();

  expect(posts).toHaveLength(3);
  expect(posts[0].body).toMatchObject({
    reason: "Consolidate synthetic delivery teams.",
    sources: [
      { expectedVersion: sourceOne.version, unitId: sourceOne.id },
      { expectedVersion: sourceTwo.version, unitId: sourceTwo.id },
    ],
    successor: { expectedVersion: successor.version, unitId: successor.id },
  });
  const reviewedPlan = posts[1].body as { dispositions: Record<string, unknown>[] };
  const actions = reviewedPlan.dispositions.reduce<Record<string, unknown>>((current, item) => {
    if (typeof item.kind === "string") current[item.kind] = item.action;
    return current;
  }, {});
  expect(actions).toEqual({
    capability: "end",
    child_unit: "move",
    delivery_profile: "end",
    grant: "revoke",
    membership: "move",
    pending_transfer: "cancel",
    task: "move",
  });
  expect(posts[2].body.plan).toEqual(posts[1].body);
  expect(posts[2].body.previewHash).toBe("a".repeat(64));
});

test("the organisation root cannot be a successor and offers no merge form", async () => {
  mockMergeApi([]);
  const root = { ...unit("1", "Root", 5), parentId: null };
  const onClose = vi.fn();
  renderWithProviders(<OrganisationMergePanel onClose={onClose} successor={root} />);

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The organisation root cannot be a merge successor.",
  );
  expect(screen.queryByRole("button", { name: "Assess dependencies" })).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Close merge" }));
  expect(onClose).toHaveBeenCalled();
});

test("at least two sources and a reason are required before assessment", async () => {
  mockMergeApi([]);
  renderWithProviders(<OrganisationMergePanel onClose={vi.fn()} successor={successor} />);

  const submit = await screen.findByRole("button", { name: "Assess dependencies" });
  expect(submit).toBeDisabled();
  await userEvent.click(await screen.findByLabelText(sourceOne.shortName));
  await userEvent.selectOptions(screen.getByLabelText("Authorising grant"), grantId);
  await userEvent.type(screen.getByLabelText("Reason"), "Consolidate synthetic delivery teams.");
  // One source is a rename, not a merge.
  expect(submit).toBeDisabled();

  await userEvent.click(screen.getByLabelText(sourceTwo.shortName));
  expect(submit).toBeEnabled();

  // Deselecting takes it back below the threshold.
  await userEvent.click(screen.getByLabelText(sourceTwo.shortName));
  expect(submit).toBeDisabled();
});

test("an assessed plan can be discarded before it is reviewed", async () => {
  const posts: { body: Record<string, unknown>; url: string }[] = [];
  mockMergeApi(posts);
  renderWithProviders(<OrganisationMergePanel onClose={vi.fn()} successor={successor} />);

  await userEvent.click(await screen.findByLabelText(sourceOne.shortName));
  await userEvent.click(screen.getByLabelText(sourceTwo.shortName));
  await userEvent.selectOptions(screen.getByLabelText("Authorising grant"), grantId);
  await userEvent.type(screen.getByLabelText("Reason"), "Consolidate synthetic delivery teams.");
  await userEvent.click(screen.getByRole("button", { name: "Assess dependencies" }));

  expect(await screen.findByText(/7 records require an explicit outcome/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Change selection" }));
  expect(screen.queryByText(/7 records require an explicit outcome/)).not.toBeInTheDocument();
  expect(screen.queryByText("Plan checked")).not.toBeInTheDocument();
  expect(posts).toHaveLength(1);
});

function mockMergeApi(posts: { body: Record<string, unknown>; url: string }[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        const body = JSON.parse(typeof init.body === "string" ? init.body : "{}") as Record<
          string,
          unknown
        >;
        posts.push({ body, url });
        if (url.endsWith("merge-assessments")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                activeChildren: 1,
                maximumResultDepth: 3,
                newlyCoveringGrants: 0,
                records,
                reservations: 0,
                savedViews: 0,
                stateDigest: "b".repeat(64),
                successorHasDeliveryProfile: false,
                teamCalendarEvents: 0,
              }),
          });
        }
        if (url.endsWith("merge-previews")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ impact: { records }, previewHash: "a".repeat(64) }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ replayed: false, sourceVersions: [], successorVersion: 6 }),
        });
      }
      if (url.includes("/grants")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              grants: [
                {
                  action: "organisation:restructure",
                  delegationDepth: 0,
                  id: grantId,
                  includeDescendants: true,
                  managerUserId: "preview-user",
                  revokedAt: null,
                  rootUnitId: parentId,
                  sourceGrantId: null,
                  validFrom: "2026-08-03T10:00:00Z",
                  validUntil: null,
                  version: 1,
                },
              ],
            }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ units: [successor, sourceOne, sourceTwo] }),
      });
    }),
  );
}

function unit(suffix: string, shortName: string, version: number) {
  return {
    category: "delivery_team" as const,
    description: "Synthetic team.",
    id: `00000000-0000-4000-8000-00000000000${suffix}`,
    isActive: true,
    name: `${shortName} Team`,
    parentId,
    shortName,
    timeZone: "Europe/London",
    validFrom: "2026-08-03T10:00:00Z",
    validUntil: null,
    version,
  };
}

function record(kind: string, suffix: string) {
  return {
    containerId: null,
    kind,
    recordId: `00000000-0000-4000-8000-0000000000${suffix}`,
    sourceUnitId: sourceOne.id,
    version: 1,
  };
}
