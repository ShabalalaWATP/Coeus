import { ApiClient, ApiError } from "./client";
import { previewSession } from "../../test/test-utils";

test("sends request id headers and returns typed JSON", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () =>
      Promise.resolve({
        status: "ok",
        service: "coeus-api",
        environment: "test",
        request_id: "req-web",
      }),
  });
  vi.stubGlobal("fetch", fetchMock);

  const response = await new ApiClient("http://api.test").getLiveness("req-web");

  expect(response.status).toBe("ok");
  expect(fetchMock).toHaveBeenCalledWith("http://api.test/api/v1/health/live", {
    credentials: "include",
    headers: { "X-Request-ID": "req-web" },
    method: "GET",
  });
});

test("omits request id headers when none are provided", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () =>
      Promise.resolve({
        status: "ok",
        service: "coeus-api",
        environment: "test",
        request_id: "req-web",
      }),
  });
  vi.stubGlobal("fetch", fetchMock);

  await new ApiClient("http://api.test").getLiveness();

  expect(fetchMock).toHaveBeenCalledWith("http://api.test/api/v1/health/live", {
    credentials: "include",
    headers: undefined,
    method: "GET",
  });
});

test("posts login payloads with credentials included", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(previewSession),
  });
  vi.stubGlobal("fetch", fetchMock);

  await new ApiClient("http://api.test").login({
    username: "admin@example.test",
    password: "CoeusLocal1!",
  });

  expect(fetchMock).toHaveBeenCalledWith("http://api.test/api/v1/auth/login", {
    body: JSON.stringify({ username: "admin@example.test", password: "CoeusLocal1!" }),
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
});

test("sends csrf header for logout", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true });
  vi.stubGlobal("fetch", fetchMock);

  await new ApiClient("http://api.test").logout("csrf-token");

  expect(fetchMock).toHaveBeenCalledWith("http://api.test/api/v1/auth/logout", {
    credentials: "include",
    headers: { "X-CSRF-Token": "csrf-token" },
    method: "POST",
  });
});

test("lists access control groups through the ACG endpoint", async () => {
  const acg = {
    id: "acg-alpha",
    code: "ACG-ALPHA",
    name: "Alpha",
    description: "Alpha access group",
    ownerUserId: null,
    isActive: true,
    memberUserIds: ["user-alpha"],
  };
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ acgs: [acg] }),
  });
  vi.stubGlobal("fetch", fetchMock);

  const response = await new ApiClient("http://api.test").listAcgs();

  expect(response).toEqual([acg]);
  expect(fetchMock).toHaveBeenCalledWith("http://api.test/api/v1/acgs", {
    credentials: "include",
    method: "GET",
  });
});

test("creates access control groups with csrf protection", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () =>
      Promise.resolve({
        id: "acg-created",
        code: "ACG-CREATED",
        name: "Created",
        description: "Created group",
        ownerUserId: null,
        isActive: true,
        memberUserIds: [],
      }),
  });
  vi.stubGlobal("fetch", fetchMock);

  await new ApiClient("http://api.test").createAcg(
    { code: "ACG-CREATED", name: "Created", description: "Created group" },
    "csrf-token",
  );

  expect(fetchMock).toHaveBeenCalledWith("http://api.test/api/v1/acgs", {
    body: JSON.stringify({
      code: "ACG-CREATED",
      name: "Created",
      description: "Created group",
    }),
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf-token" },
    method: "POST",
  });
});

test("updates ACG metadata and membership through protected endpoints", async () => {
  const updatedAcg = {
    id: "acg-alpha",
    code: "ACG-ALPHA",
    name: "Alpha Updated",
    description: "Updated group",
    ownerUserId: null,
    isActive: false,
    memberUserIds: ["user-alpha"],
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(updatedAcg) })
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ ...updatedAcg, memberUserIds: ["user-alpha", "user-bravo"] }),
    });
  vi.stubGlobal("fetch", fetchMock);

  const client = new ApiClient("http://api.test");
  await client.updateAcg("acg-alpha", { name: "Alpha Updated", isActive: false }, "csrf-token");
  await client.addAcgMember("acg-alpha", "user-bravo", "csrf-token");

  expect(fetchMock).toHaveBeenNthCalledWith(1, "http://api.test/api/v1/acgs/acg-alpha", {
    body: JSON.stringify({ name: "Alpha Updated", isActive: false }),
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf-token" },
    method: "PATCH",
  });
  expect(fetchMock).toHaveBeenNthCalledWith(2, "http://api.test/api/v1/acgs/acg-alpha/members", {
    body: JSON.stringify({ userId: "user-bravo" }),
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf-token" },
    method: "POST",
  });
});

test("lists project workspaces and requests access diagnostics", async () => {
  const project = {
    id: "project-1",
    reference: "PRJ-1",
    name: "Project One",
    summary: "Workspace summary",
    requesterUserId: "user-1",
    acgIds: ["acg-1"],
    ticketIds: ["ticket-1"],
    members: [],
    milestones: [],
    planItems: [],
    visibleProducts: [],
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ projects: [project] }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(project),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          allowed: false,
          reason: "Denied",
          checks: [{ name: "acg_membership", passed: false, reason: "Missing ACG" }],
        }),
    });
  vi.stubGlobal("fetch", fetchMock);

  const client = new ApiClient("http://api.test");
  await expect(client.listProjects()).resolves.toEqual([project]);
  await expect(client.getProject("project-1")).resolves.toMatchObject({ name: "Project One" });
  await expect(client.diagnoseProductAccess("product-1", "user-1")).resolves.toMatchObject({
    allowed: false,
  });

  expect(fetchMock).toHaveBeenNthCalledWith(1, "http://api.test/api/v1/projects", {
    credentials: "include",
    method: "GET",
  });
  expect(fetchMock).toHaveBeenNthCalledWith(2, "http://api.test/api/v1/projects/project-1", {
    credentials: "include",
    method: "GET",
  });
  expect(fetchMock).toHaveBeenNthCalledWith(
    3,
    "http://api.test/api/v1/store/products/product-1/access-diagnostics",
    {
      body: JSON.stringify({ userId: "user-1" }),
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      method: "POST",
    },
  );
});

test("throws parsed API errors on logout failures", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: () => Promise.resolve({ error: { code: "csrf_failed", message: "CSRF failed." } }),
    }),
  );

  await expect(new ApiClient("http://api.test").logout("bad-csrf")).rejects.toEqual(
    new ApiError(403, "csrf_failed", "CSRF failed."),
  );
});

test("throws parsed API errors on non-success responses", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 423,
      json: () =>
        Promise.resolve({
          error: { code: "account_locked", message: "Authentication temporarily locked." },
        }),
    }),
  );

  await expect(new ApiClient("http://api.test").getCurrentUser()).rejects.toEqual(
    new ApiError(423, "account_locked", "Authentication temporarily locked."),
  );
});

test("uses fallback API error details when the response body is not JSON", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.reject(new Error("invalid json")),
    }),
  );

  await expect(new ApiClient("http://api.test").getCurrentUser()).rejects.toEqual(
    new ApiError(500, "request_failed", "API request failed with status 500"),
  );
});
