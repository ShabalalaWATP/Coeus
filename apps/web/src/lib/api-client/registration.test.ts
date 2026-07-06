import { ApiError } from "./client";
import {
  approveRegistration,
  listPendingRegistrations,
  rejectRegistration,
  submitRegistration,
} from "./registration";

afterEach(() => {
  vi.restoreAllMocks();
});

test("calls registration endpoints with CSRF-protected decisions", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ registrations: [] }),
  });
  vi.stubGlobal("fetch", fetchMock);

  await submitRegistration({
    username: "new.operator@example.test",
    displayName: "New Operator",
    justification: "",
    password: "NewOperator1!x",
  });
  await listPendingRegistrations();
  await approveRegistration("registration-1", "csrf");
  await rejectRegistration("registration-1", "Duties not confirmed.", "csrf");

  expect(fetchMock).toHaveBeenNthCalledWith(
    1,
    "http://127.0.0.1:8001/api/v1/auth/register",
    expect.objectContaining({ method: "POST", credentials: "include" }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(2, "http://127.0.0.1:8001/api/v1/admin/registrations", {
    credentials: "include",
    method: "GET",
  });
  expect(fetchMock).toHaveBeenNthCalledWith(
    3,
    "http://127.0.0.1:8001/api/v1/admin/registrations/registration-1/approve",
    { credentials: "include", headers: { "X-CSRF-Token": "csrf" }, method: "POST" },
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    4,
    "http://127.0.0.1:8001/api/v1/admin/registrations/registration-1/reject",
    expect.objectContaining({
      body: JSON.stringify({ reason: "Duties not confirmed." }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
      method: "POST",
    }),
  );
});

test("converts registration API errors", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: () =>
        Promise.resolve({ error: { code: "registration_throttled", message: "Too many." } }),
    }),
  );

  await expect(
    submitRegistration({
      username: "new.operator@example.test",
      displayName: "New Operator",
      justification: "",
      password: "NewOperator1!x",
    }),
  ).rejects.toEqual(new ApiError(429, "registration_throttled", "Too many."));
});
