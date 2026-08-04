import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { OrganisationSplitPanel } from "./OrganisationSplitPanel";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const parent = unit("1", "Parent", 6, null);
const source = unit("2", "Source", 4, parent.id);
const grantId = "00000000-0000-4000-8000-000000000003";
const records = [
  record("child_unit", "11"),
  record("membership", "12"),
  record("task", "13"),
  record("grant", "14"),
  record("delivery_profile", "15"),
  record("capability", "16"),
  record("pending_transfer", "17"),
];

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("assigns movable dependencies and executes the exact reviewed split plan", async () => {
  const posts: { body: Record<string, unknown>; url: string }[] = [];
  mockSplitApi(posts);
  renderWithProviders(<OrganisationSplitPanel onClose={vi.fn()} source={source} />);

  const names = screen.getAllByLabelText("Name");
  const shortNames = screen.getAllByLabelText("Short name");
  await userEvent.type(names[0], "Synthetic Alpha");
  await userEvent.type(shortNames[0], "Alpha");
  await userEvent.type(names[1], "Synthetic Bravo");
  await userEvent.type(shortNames[1], "Bravo");
  await screen.findAllByRole("option", { name: "Descendant scope" });
  await userEvent.selectOptions(screen.getByLabelText("Source authority"), grantId);
  await userEvent.selectOptions(screen.getByLabelText("Parent authority"), grantId);
  await userEvent.type(screen.getByLabelText("Reason"), "Separate synthetic mission groups.");
  await userEvent.click(screen.getByRole("button", { name: "Assess dependencies" }));

  const request = posts[0].body as { successors: { shortName: string; unitId: string }[] };
  await screen.findByText(/Choose the successor for each movable record group/);
  await userEvent.selectOptions(
    screen.getByLabelText("membership destination"),
    request.successors[1].unitId,
  );
  await userEvent.click(screen.getByRole("button", { name: "Review split plan" }));
  expect(await screen.findByText("Plan checked")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Confirm split" }));
  expect(await screen.findByText("Unit split successfully.")).toBeVisible();

  expect(posts).toHaveLength(3);
  expect(posts[0].body).toMatchObject({
    parent: { expectedVersion: parent.version, unitId: parent.id },
    parentAuthorisingGrantId: grantId,
    reason: "Separate synthetic mission groups.",
    source: { expectedVersion: source.version, unitId: source.id },
    sourceAuthorisingGrantId: grantId,
  });
  const plan = posts[1].body as { dispositions: Record<string, unknown>[] };
  const membership = plan.dispositions.find((item) => item.kind === "membership");
  expect(membership).toMatchObject({ action: "move", targetUnitId: request.successors[1].unitId });
  expect(membership?.replacementId).toEqual(expect.any(String));
  expect(plan.dispositions.find((item) => item.kind === "grant")).toMatchObject({
    action: "revoke",
    targetUnitId: null,
  });
  expect(posts[2].body.plan).toEqual(posts[1].body);
  expect(posts[2].body.previewHash).toBe("c".repeat(64));
});

test("successors can be added and removed, and re-assessment discards a stale plan", async () => {
  const posts: { body: Record<string, unknown>; url: string }[] = [];
  mockSplitApi(posts);
  renderWithProviders(<OrganisationSplitPanel onClose={vi.fn()} source={source} />);

  // Two successors are the minimum, so neither is removable until a third exists.
  expect(screen.queryByRole("button", { name: "Remove" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /Add successor/ }));
  expect(screen.getAllByLabelText("Name")).toHaveLength(3);
  expect(screen.getAllByRole("button", { name: "Remove" })).toHaveLength(3);

  await userEvent.click(screen.getAllByRole("button", { name: "Remove" })[2]);
  expect(screen.getAllByLabelText("Name")).toHaveLength(2);

  const names = screen.getAllByLabelText("Name");
  const shortNames = screen.getAllByLabelText("Short name");
  await userEvent.type(names[0], "Synthetic Alpha");
  await userEvent.type(shortNames[0], "Alpha");
  await userEvent.type(names[1], "Synthetic Bravo");
  await userEvent.type(shortNames[1], "Bravo");
  await screen.findAllByRole("option", { name: "Descendant scope" });

  // Authority and a reason are all required before dependencies can be assessed.
  expect(screen.getByRole("button", { name: "Assess dependencies" })).toBeDisabled();
  await userEvent.selectOptions(screen.getByLabelText("Source authority"), grantId);
  await userEvent.selectOptions(screen.getByLabelText("Parent authority"), grantId);
  expect(screen.getByRole("button", { name: "Assess dependencies" })).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Reason"), "Separate synthetic mission groups.");
  await userEvent.click(screen.getByRole("button", { name: "Assess dependencies" }));

  await screen.findByText(/Choose the successor for each movable record group/);
  await userEvent.click(screen.getByRole("button", { name: "Change definition" }));
  expect(
    screen.queryByText(/Choose the successor for each movable record group/),
  ).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Assess dependencies" })).toBeEnabled();
});

function mockSplitApi(posts: { body: Record<string, unknown>; url: string }[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        const body = JSON.parse(typeof init.body === "string" ? init.body : "{}") as Record<
          string,
          unknown
        >;
        posts.push({ body, url });
        if (url.endsWith("split-assessments")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                records,
                reservations: 0,
                savedViews: 0,
                stateDigest: "d".repeat(64),
                teamCalendarEvents: 0,
              }),
          });
        }
        if (url.endsWith("split-previews")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ impact: { records }, previewHash: "c".repeat(64) }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ replayed: false, successors: [] }),
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
                  rootUnitId: parent.id,
                  sourceGrantId: null,
                  validFrom: "2026-08-03T10:00:00Z",
                  validUntil: null,
                  version: 1,
                },
              ],
            }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve(parent) });
    }),
  );
}

function unit(suffix: string, shortName: string, version: number, parentId: string | null) {
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
    sourceUnitId: source.id,
    version: 1,
  };
}
