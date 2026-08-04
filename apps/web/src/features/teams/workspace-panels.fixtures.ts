/** Shared stubs for the integrated team workspace panel tests. */

export function ok(payload: unknown) {
  return Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve(payload),
    blob: () => Promise.resolve(new Blob(["scope,metric"], { type: "text/csv" })),
  });
}

export function failure(status = 500) {
  return Promise.resolve({
    ok: false,
    status,
    json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
  });
}

export function stub(handler: (url: string, init?: RequestInit) => unknown) {
  const fetchMock = vi.fn(handler);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

/** These requests always send a JSON string body; read it without stringifying. */
export function jsonBody(init: RequestInit | undefined): unknown {
  const body = init?.body;
  return typeof body === "string" ? JSON.parse(body) : undefined;
}

export const person = {
  userId: "user-1",
  displayName: "Synthetic Analyst",
  membershipRole: "team_member",
  assignmentEligible: true,
  workingPattern: "37h week",
};

export const policy = {
  unitId: "unit-1",
  wipLimit: 8,
  serviceTargetHours: 72,
  planningCadence: "weekly",
  planningWeekday: 0,
  planningLocalTime: "09:00:00",
  planningDurationMinutes: 60,
  version: 3,
  deliveryPolicyVersion: 2,
  updatedAt: "2026-08-03T12:00:00Z",
};
