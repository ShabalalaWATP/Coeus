import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { OrganisationCutoverReleasePanel } from "./OrganisationCutoverReleasePanel";
import { HASH_FIELDS, REFERENCE_FIELDS } from "./cutover-manifest";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const digest = "a".repeat(64);
const otherDigest = "b".repeat(64);
const manifest = {
  sourceRevision: "release-2026.08",
  schemaHead: "20260804_0045",
  organisationParityHash: digest,
  calendarParityHash: digest,
  taskCapacityParityHash: digest,
  routingEvaluationRelease: "routing-v3",
  routingEvaluationHash: digest,
  protectedChecksReference: "ci/run/123",
  protectedChecksHash: digest,
  browserEvidenceHash: digest,
  securityReviewReference: "security/review/123",
  securityReviewHash: digest,
  backupRestoreHash: digest,
};

const emptySlice = (slice: string) => ({
  slice,
  status: "not_previewed",
  previewDigest: null,
  proposedByUserId: null,
  approvals: [],
  activatedByUserId: null,
  activatedAt: null,
});

const previewedSlice = (slice: string, proposer = "another-administrator") => ({
  ...emptySlice(slice),
  status: "previewed",
  previewDigest: otherDigest,
  proposedByUserId: proposer,
});

const release = {
  candidateDigest: digest,
  manifest,
  slices: [previewedSlice("organisation"), emptySlice("calendar"), emptySlice("task_capacity")],
  eligible: false,
};

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("shows three bounded slices and explains the four-person ceremony", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => ok(release)),
  );
  renderWithProviders(<OrganisationCutoverReleasePanel />, "/admin/organisation");

  expect(
    await screen.findByRole("heading", { name: "Release activation is blocked" }),
  ).toBeVisible();
  expect(screen.getByText(/four-person separation of duties applies/i)).toBeVisible();
  expect(screen.getByText(/this page never activates a service/i)).toBeVisible();
  expect(screen.getByRole("heading", { name: "Organisation and authority" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Calendars and availability" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Tasks and capacity" })).toBeVisible();
  expect(screen.queryByDisplayValue("release-2026.08")).not.toBeVisible();
  expect(screen.queryByRole("button", { name: /activate/i })).not.toBeInTheDocument();

  await userEvent.click(screen.getByText("Candidate evidence"));
  expect(screen.getByDisplayValue("release-2026.08")).toBeDisabled();
});

test("previews one exact slice without changing service authority", async () => {
  const calls: { url: string; init?: RequestInit }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url.endsWith("/previews/calendar")) {
        return ok({
          slice: "calendar",
          candidateDigest: digest,
          previewDigest: otherDigest,
          proposedByUserId: "preview-user",
          expiresAt: "2026-08-04T09:00:00Z",
        });
      }
      return ok(release);
    }),
  );
  renderWithProviders(<OrganisationCutoverReleasePanel />, "/admin/organisation");

  const calendar = await screen.findByRole("heading", { name: "Calendars and availability" });
  const card = calendar.closest("article");
  expect(card).not.toBeNull();
  await userEvent.click(within(card!).getByRole("button", { name: "Preview impact" }));

  await waitFor(() =>
    expect(calls.some((call) => call.url.endsWith("/previews/calendar"))).toBe(true),
  );
  const previewCall = calls.find((call) => call.url.endsWith("/previews/calendar"));
  expect(previewCall?.init?.headers).toMatchObject({ "X-CSRF-Token": "test-csrf-token" });
  expect(jsonBody(previewCall?.init)).toEqual(manifest);
});

test("reauthenticates an independent reviewer and sends the exact preview", async () => {
  let approvalBody: Record<string, unknown> | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (url.endsWith("/approvals")) {
        approvalBody = jsonBody(init) as Record<string, unknown>;
        return ok({
          approvalId: "approval-1",
          slice: "organisation",
          candidateDigest: digest,
          previewDigest: otherDigest,
          approvalRole: "security_review",
          approvedByUserId: "preview-user",
          approvedAt: "2026-08-04T08:00:00Z",
        });
      }
      return ok(release);
    }),
  );
  renderWithProviders(<OrganisationCutoverReleasePanel />, "/admin/organisation");

  await userEvent.click(
    await screen.findByRole("button", { name: "Approve as security reviewer" }),
  );
  await userEvent.type(screen.getByLabelText("Current password"), "current-password");
  await userEvent.click(screen.getByRole("button", { name: "Confirm approval" }));

  await waitFor(() => expect(approvalBody).toBeDefined());
  expect(approvalBody).toEqual({
    slice: "organisation",
    candidateDigest: digest,
    previewDigest: otherDigest,
    approvalRole: "security_review",
    currentPassword: "current-password",
  });
  expect(screen.queryByDisplayValue("current-password")).not.toBeInTheDocument();
});

test("prevents the proposer from approving their own preview", async () => {
  const proposed = {
    ...release,
    slices: [
      previewedSlice("organisation", "preview-user"),
      emptySlice("calendar"),
      emptySlice("task_capacity"),
    ],
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(() => ok(proposed)),
  );
  renderWithProviders(<OrganisationCutoverReleasePanel />, "/admin/organisation");

  expect(await screen.findByText(/you already participated in this slice/i)).toBeVisible();
  expect(screen.queryByRole("button", { name: /approve as/i })).not.toBeInTheDocument();
});

test("fails closed when release status is incomplete", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => ok({ ...release, slices: [] })),
  );
  renderWithProviders(<OrganisationCutoverReleasePanel />, "/admin/organisation");

  expect(
    await screen.findByRole("heading", { name: "Release status could not be verified" }),
  ).toBeVisible();
  expect(screen.getByText(/all cutover actions are blocked/i)).toBeVisible();
  expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
});

test("evidence must be complete before any slice can be previewed", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      ok({
        candidateDigest: null,
        manifest: null,
        eligible: false,
        slices: [emptySlice("organisation"), emptySlice("calendar"), emptySlice("task_capacity")],
      }),
    ),
  );
  renderWithProviders(<OrganisationCutoverReleasePanel />, "/admin/organisation");

  expect(await screen.findByText(/no release candidate has been recorded/i)).toBeVisible();
  const previews = screen.getAllByRole("button", { name: "Preview impact" });
  expect(previews.every((button) => (button as HTMLButtonElement).disabled)).toBe(true);

  await userEvent.click(screen.getByText("Enter candidate evidence"));
  for (const [, label] of REFERENCE_FIELDS) {
    fireEvent.change(screen.getByLabelText(label), { target: { value: " ci/run/9 " } });
  }
  // Entered in upper case to prove digests are normalised before they are held.
  for (const [, label] of HASH_FIELDS) {
    fireEvent.change(screen.getByLabelText(label), { target: { value: "A".repeat(64) } });
  }

  expect(screen.getByLabelText("Source revision")).toHaveValue("ci/run/9");
  expect(screen.getByLabelText("Organisation parity evidence")).toHaveValue("a".repeat(64));
  await waitFor(() =>
    expect(screen.getAllByRole("button", { name: "Preview impact" })[0]).toBeEnabled(),
  );
});

test("a rejected preview is reported and the slice can be previewed again", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.endsWith("/previews/organisation")) {
        return Promise.resolve({
          ok: false,
          status: 409,
          json: () =>
            Promise.resolve({
              error: { code: "conflict", message: "Evidence no longer matches the candidate." },
            }),
        });
      }
      return ok(release);
    }),
  );
  renderWithProviders(<OrganisationCutoverReleasePanel />, "/admin/organisation");

  const card = (await screen.findByRole("heading", { name: "Organisation and authority" })).closest(
    "article",
  );
  // A previewed slice offers a refresh rather than a first preview.
  await userEvent.click(within(card!).getByRole("button", { name: "Refresh preview" }));

  expect(await within(card!).findByRole("alert")).toHaveTextContent("Preview failed:");
});

test("a rejected approval is reported and the reviewer can cancel", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.endsWith("/approvals")) {
        return Promise.resolve({
          ok: false,
          status: 401,
          json: () =>
            Promise.resolve({ error: { code: "unauthorised", message: "Password rejected." } }),
        });
      }
      return ok(release);
    }),
  );
  renderWithProviders(<OrganisationCutoverReleasePanel />, "/admin/organisation");

  await userEvent.click(
    await screen.findByRole("button", { name: "Approve as security reviewer" }),
  );
  await userEvent.type(screen.getByLabelText("Current password"), "wrong-password");
  await userEvent.click(screen.getByRole("button", { name: "Confirm approval" }));

  expect(await screen.findByText(/approval failed:/i)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.queryByLabelText("Current password")).not.toBeInTheDocument();
});

test("an activated release states that it is verified and offers no further action", async () => {
  const approval = (role: string, approver: string) => ({
    approvalId: `approval-${role}`,
    slice: "organisation",
    candidateDigest: digest,
    previewDigest: otherDigest,
    approvalRole: role,
    approvedByUserId: approver,
    approvedAt: "2026-08-04T08:00:00Z",
  });
  const activeSlice = (slice: string) => ({
    ...previewedSlice(slice),
    status: "active",
    approvals: [
      { ...approval("security_review", "reviewer"), slice },
      { ...approval("release_authority", "authority"), slice },
    ],
    activatedByUserId: "executor",
    activatedAt: "2026-08-04T09:00:00Z",
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      ok({
        candidateDigest: digest,
        manifest,
        eligible: true,
        slices: [
          activeSlice("organisation"),
          activeSlice("calendar"),
          activeSlice("task_capacity"),
        ],
      }),
    ),
  );
  renderWithProviders(<OrganisationCutoverReleasePanel />, "/admin/organisation");

  expect(
    await screen.findByRole("heading", { name: "Release is active and verified" }),
  ).toBeVisible();
  expect(screen.getAllByLabelText("Active")).toHaveLength(3);
  expect(screen.queryByRole("button", { name: /preview/i })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /approve as/i })).not.toBeInTheDocument();
});

test("a failed release read can be retried", async () => {
  const fetchMock = vi.fn(() =>
    Promise.resolve({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<OrganisationCutoverReleasePanel />, "/admin/organisation");

  expect(
    await screen.findByRole("heading", { name: "Release status could not be verified" }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(1));
});

function ok(value: unknown) {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(value) });
}

/** These requests always send a JSON string body; read it without stringifying. */
function jsonBody(init: RequestInit | undefined): unknown {
  const body = init?.body;
  return typeof body === "string" ? JSON.parse(body) : undefined;
}
