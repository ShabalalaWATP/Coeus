import {
  addAccessGroupAdmin,
  applyForAccessGroup,
  decideAccessGroupApplication,
  listAccessGroupAdmins,
  listAccessGroupApplications,
  listAccessGroups,
  removeAccessGroupAdmin,
  searchAccessGroupDirectory,
  withdrawAccessGroupApplication,
  type AccessGroupApplication,
} from "./access-groups";

afterEach(() => vi.unstubAllGlobals());

const application: AccessGroupApplication = {
  id: "application/1",
  acgId: "acg/1",
  acgName: "Regional reporting",
  applicantUserId: "user-1",
  applicantDisplayName: "Requesting User",
  justification: "Assigned work requires access.",
  status: "pending",
  submittedAt: "2026-07-12T10:00:00Z",
};

test("uses the bounded catalogue and application workflow contracts", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ applications: [application], acgs: [] }),
  });
  vi.stubGlobal("fetch", fetchMock);

  await listAccessGroups(2, " cyber ");
  await applyForAccessGroup("acg/1", application.justification, "csrf");
  await withdrawAccessGroupApplication("acg/1", "csrf");
  await listAccessGroupApplications(3);
  await decideAccessGroupApplication(application, "approve", "ignored", "csrf");
  await decideAccessGroupApplication(application, "reject", "Insufficient need.", "csrf");

  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/acgs/catalogue?page=2&pageSize=50&query=cyber",
    expect.objectContaining({ method: "GET" }),
  );
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/acgs/acg%2F1/applications/mine",
    expect.objectContaining({ method: "DELETE" }),
  );
  expect(fetchMock).toHaveBeenLastCalledWith(
    "http://127.0.0.1:8001/api/v1/acg-applications/application%2F1/decision",
    expect.objectContaining({
      body: JSON.stringify({ decision: "reject", reason: "Insufficient need." }),
      method: "POST",
    }),
  );
});

test("uses narrow delegated-administrator directory and roster contracts", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ admins: [], users: [], total: 0 }),
  });
  vi.stubGlobal("fetch", fetchMock);

  await listAccessGroupAdmins("acg/1");
  await addAccessGroupAdmin("acg/1", "user/2", "csrf");
  await removeAccessGroupAdmin("acg/1", "user/2", "csrf");
  await searchAccessGroupDirectory("alex orr");

  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/acgs/acg%2F1/admins/user%2F2",
    expect.objectContaining({ method: "PUT" }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    3,
    "http://127.0.0.1:8001/api/v1/acgs/acg%2F1/admins/user%2F2",
    expect.objectContaining({ method: "DELETE" }),
  );
  expect(fetchMock).toHaveBeenLastCalledWith(
    "http://127.0.0.1:8001/api/v1/acgs/admin-directory?query=alex%20orr",
    expect.objectContaining({ method: "GET" }),
  );
});
