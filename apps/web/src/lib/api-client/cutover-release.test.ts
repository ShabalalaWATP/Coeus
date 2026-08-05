import {
  approveCutoverSlice,
  CUTOVER_SLICES,
  getCutoverRelease,
  previewCutoverSlice,
  type CutoverManifest,
} from "./cutover-release";

afterEach(() => vi.restoreAllMocks());

const CANDIDATE = "a".repeat(64);
const PREVIEW = "b".repeat(64);

const manifest: CutoverManifest = {
  sourceRevision: "abc1234",
  schemaHead: "20260804_0044",
  organisationParityHash: "c".repeat(64),
  calendarParityHash: "d".repeat(64),
  taskCapacityParityHash: "e".repeat(64),
  routingEvaluationRelease: "routing:v1",
  routingEvaluationHash: "f".repeat(64),
  protectedChecksReference: "run/1",
  protectedChecksHash: "0".repeat(64),
  browserEvidenceHash: "1".repeat(64),
  securityReviewReference: "review/1",
  securityReviewHash: "2".repeat(64),
  backupRestoreHash: "3".repeat(64),
};

function approval(role: string, approver: string) {
  return {
    approvalId: "approval-" + role,
    slice: "organisation",
    candidateDigest: CANDIDATE,
    previewDigest: PREVIEW,
    approvalRole: role,
    approvedByUserId: approver,
    approvedAt: "2026-08-03T12:00:00Z",
  };
}

function activeSlice(slice: string) {
  return {
    slice,
    status: "active",
    previewDigest: PREVIEW,
    proposedByUserId: "proposer",
    approvals: [
      { ...approval("security_review", "reviewer"), slice },
      { ...approval("release_authority", "authority"), slice },
    ],
    activatedByUserId: "activator",
    activatedAt: "2026-08-03T13:00:00Z",
  };
}

function release(overrides: Record<string, unknown> = {}) {
  return {
    candidateDigest: CANDIDATE,
    manifest,
    slices: CUTOVER_SLICES.map(activeSlice),
    eligible: true,
    ...overrides,
  };
}

function stub(payload: unknown, ok = true) {
  const fetchMock = vi.fn(() =>
    Promise.resolve({ ok, status: ok ? 200 : 500, json: () => Promise.resolve(payload) }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

test("accepts a complete, fully approved release", async () => {
  stub(release());

  const state = await getCutoverRelease();

  expect(state.eligible).toBe(true);
  expect(state.candidateDigest).toBe(CANDIDATE);
  expect(state.manifest?.schemaHead).toBe("20260804_0044");
  expect(state.slices).toHaveLength(3);
  expect(state.slices[0]?.approvals).toHaveLength(2);
});

test("accepts a release that has never been previewed", async () => {
  stub(
    release({
      candidateDigest: null,
      manifest: null,
      eligible: false,
      slices: CUTOVER_SLICES.map((slice) => ({
        slice,
        status: "not_previewed",
        previewDigest: null,
        proposedByUserId: null,
        approvals: [],
        activatedByUserId: null,
        activatedAt: null,
      })),
    }),
  );

  const state = await getCutoverRelease();

  expect(state.candidateDigest).toBeNull();
  expect(state.manifest).toBeNull();
  expect(state.eligible).toBe(false);
});

test.each([
  ["a non-object payload", []],
  ["a missing slice list", { candidateDigest: null, manifest: null, eligible: false }],
  ["a non-boolean eligibility", release({ eligible: "yes" })],
])("refuses %s as incomplete", async (_label, payload) => {
  stub(payload);

  await expect(getCutoverRelease()).rejects.toThrow("The release status is incomplete");
});

test.each([
  ["a partial slice set", release({ slices: [activeSlice("organisation")] })],
  [
    "a duplicated slice",
    release({
      slices: [activeSlice("organisation"), activeSlice("organisation"), activeSlice("calendar")],
    }),
  ],
  ["a malformed candidate digest", release({ candidateDigest: "not-a-digest" })],
  ["a manifest without a candidate", release({ candidateDigest: null })],
  ["a candidate without a manifest", release({ manifest: null })],
  [
    "an eligible release with unfinished slices",
    release({
      slices: [
        { ...activeSlice("organisation"), status: "approved" },
        activeSlice("calendar"),
        activeSlice("task_capacity"),
      ],
    }),
  ],
])("refuses %s as inconsistent", async (_label, payload) => {
  stub(payload);

  await expect(getCutoverRelease()).rejects.toThrow("The release status is inconsistent");
});

test("refuses an un-previewed release that claims progress", async () => {
  stub(
    release({
      candidateDigest: null,
      manifest: null,
      eligible: false,
      slices: CUTOVER_SLICES.map((slice) => ({
        slice,
        status: "previewed",
        previewDigest: PREVIEW,
        proposedByUserId: "proposer",
        approvals: [],
        activatedByUserId: null,
        activatedAt: null,
      })),
    }),
  );

  await expect(getCutoverRelease()).rejects.toThrow("The release status is inconsistent");
});

test.each([
  [
    "an approval reused by the proposer",
    {
      ...activeSlice("organisation"),
      approvals: [
        { ...approval("security_review", "proposer"), slice: "organisation" },
        { ...approval("release_authority", "authority"), slice: "organisation" },
      ],
    },
  ],
  [
    "two approvals from one person",
    {
      ...activeSlice("organisation"),
      approvals: [
        { ...approval("security_review", "reviewer"), slice: "organisation" },
        { ...approval("release_authority", "reviewer"), slice: "organisation" },
      ],
    },
  ],
  [
    "two approvals in the same role",
    {
      ...activeSlice("organisation"),
      approvals: [
        { ...approval("security_review", "reviewer"), slice: "organisation" },
        { ...approval("security_review", "authority"), slice: "organisation" },
      ],
    },
  ],
  [
    "an approval bound to another candidate",
    {
      ...activeSlice("organisation"),
      approvals: [
        {
          ...approval("security_review", "reviewer"),
          slice: "organisation",
          candidateDigest: "9".repeat(64),
        },
        { ...approval("release_authority", "authority"), slice: "organisation" },
      ],
    },
  ],
  [
    "an approval bound to another preview",
    {
      ...activeSlice("organisation"),
      approvals: [
        {
          ...approval("security_review", "reviewer"),
          slice: "organisation",
          previewDigest: "9".repeat(64),
        },
        { ...approval("release_authority", "authority"), slice: "organisation" },
      ],
    },
  ],
  [
    "an approval for another slice",
    {
      ...activeSlice("organisation"),
      approvals: [
        { ...approval("security_review", "reviewer"), slice: "calendar" },
        { ...approval("release_authority", "authority"), slice: "organisation" },
      ],
    },
  ],
  ["a preview digest that is not a digest", { ...activeSlice("organisation"), previewDigest: "x" }],
  ["a preview with no proposer", { ...activeSlice("organisation"), proposedByUserId: null }],
  [
    "an untouched slice carrying a preview",
    { ...activeSlice("organisation"), status: "not_previewed" },
  ],
  [
    "an approved slice with a single approval",
    {
      ...activeSlice("organisation"),
      status: "approved",
      approvals: [{ ...approval("security_review", "reviewer"), slice: "organisation" }],
    },
  ],
  [
    "an active slice with no activation record",
    { ...activeSlice("organisation"), activatedAt: null },
  ],
])("refuses %s in the slice lineage", async (_label, slice) => {
  stub(
    release({
      eligible: false,
      slices: [slice, activeSlice("calendar"), activeSlice("task_capacity")],
    }),
  );

  await expect(getCutoverRelease()).rejects.toThrow("The release status is inconsistent");
});

test.each([
  ["an unknown slice name", { ...activeSlice("organisation"), slice: "people" }],
  ["an unknown status", { ...activeSlice("organisation"), status: "half_done" }],
  ["a non-array approval list", { ...activeSlice("organisation"), approvals: {} }],
  ["a non-object slice", "organisation"],
])("refuses %s as an invalid slice", async (_label, slice) => {
  stub(release({ slices: [slice, activeSlice("calendar"), activeSlice("task_capacity")] }));

  await expect(getCutoverRelease()).rejects.toThrow("A release slice has an invalid status");
});

test("refuses approval evidence with an unknown role", async () => {
  stub(
    release({
      slices: [
        {
          ...activeSlice("organisation"),
          approvals: [{ ...approval("auditor", "reviewer"), slice: "organisation" }],
        },
        activeSlice("calendar"),
        activeSlice("task_capacity"),
      ],
    }),
  );

  await expect(getCutoverRelease()).rejects.toThrow("Release approval evidence is invalid");
});

test.each([
  ["a non-object manifest", "manifest"],
  ["a manifest missing a field", { ...manifest, backupRestoreHash: undefined }],
])("refuses %s", async (_label, value) => {
  stub(release({ manifest: value }));

  await expect(getCutoverRelease()).rejects.toThrow("The release manifest is invalid");
});

test("posts previews and approvals with CSRF protection", async () => {
  const fetchMock = stub({
    slice: "organisation",
    candidateDigest: CANDIDATE,
    previewDigest: PREVIEW,
    proposedByUserId: "proposer",
    expiresAt: "2026-08-03T14:00:00Z",
  });

  await previewCutoverSlice("organisation", manifest, "csrf");
  await approveCutoverSlice(
    {
      slice: "organisation",
      candidateDigest: CANDIDATE,
      previewDigest: PREVIEW,
      approvalRole: "security_review",
      currentPassword: "reauthentication",
    },
    "csrf",
  );

  const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
  expect(calls[0]?.[0]).toContain("/cutover-release/previews/organisation");
  expect(calls[1]?.[0]).toContain("/cutover-release/approvals");
  for (const [, init] of calls) {
    expect(init.method).toBe("POST");
    expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("csrf");
  }
  expect(jsonBody(calls[1]?.[1])).toMatchObject({
    approvalRole: "security_review",
    currentPassword: "reauthentication",
  });
});

/** These requests always send a JSON string body; read it without stringifying. */
function jsonBody(init: RequestInit | undefined): unknown {
  const body = init?.body;
  return typeof body === "string" ? JSON.parse(body) : undefined;
}
