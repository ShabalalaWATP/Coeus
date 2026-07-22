import { addAcgMember, createAcg, listAcgs, removeAcgMember, updateAcg } from "./access";

afterEach(() => vi.unstubAllGlobals());

const acg = {
  id: "acg-alpha",
  code: "ACG-ALPHA",
  name: "Alpha",
  description: "Alpha access group",
  ownerUserId: null,
  isActive: true,
  memberUserIds: ["user-alpha"],
};

test("lists and creates access control groups", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ acgs: [acg] }) })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(acg) });
  vi.stubGlobal("fetch", fetchMock);

  await expect(listAcgs()).resolves.toEqual([acg]);
  await createAcg({ code: acg.code, name: acg.name, description: acg.description }, "csrf-token");

  expect(fetchMock).toHaveBeenNthCalledWith(2, "http://127.0.0.1:8001/api/v1/acgs", {
    body: JSON.stringify({ code: acg.code, name: acg.name, description: acg.description }),
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf-token" },
    method: "POST",
  });
});

test("updates ACG metadata and membership through protected endpoints", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(acg) })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(acg) })
    .mockResolvedValueOnce({ ok: true });
  vi.stubGlobal("fetch", fetchMock);

  await updateAcg("acg/alpha", { name: "Updated", isActive: false }, "csrf-token");
  await addAcgMember("acg/alpha", "user/bravo", "csrf-token");
  await removeAcgMember("acg/alpha", "user/bravo", "csrf-token");

  expect(fetchMock).toHaveBeenNthCalledWith(
    1,
    "http://127.0.0.1:8001/api/v1/acgs/acg%2Falpha",
    expect.any(Object),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/acgs/acg%2Falpha/members",
    expect.any(Object),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    3,
    "http://127.0.0.1:8001/api/v1/acgs/acg%2Falpha/members/user%2Fbravo",
    expect.any(Object),
  );
});
