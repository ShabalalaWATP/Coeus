import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { RegistrationApprovalsPanel } from "./RegistrationApprovalsPanel";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const pendingRegistration = {
  id: "registration-1",
  username: "new.operator@example.test",
  displayName: "New Operator",
  justification: "Mock regional reporting duties.",
  status: "pending",
  createdAt: "2026-07-06T00:00:00Z",
};

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("approves a pending access request", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ registrations: [pendingRegistration] }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ ...pendingRegistration, status: "approved" }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(
    <RegistrationApprovalsPanel csrfToken="test-csrf-token" />,
    "/admin/overview",
  );

  expect(await screen.findByText("New Operator")).toBeVisible();
  expect(screen.getByText("Mock regional reporting duties.")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Approve" }));

  expect(await screen.findByText("No pending access requests")).toBeVisible();
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/admin/registrations/registration-1/approve",
    { credentials: "include", headers: { "X-CSRF-Token": "test-csrf-token" }, method: "POST" },
  );
});

test("rejects a pending access request with a reason", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ registrations: [pendingRegistration] }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ ...pendingRegistration, status: "rejected" }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(
    <RegistrationApprovalsPanel csrfToken="test-csrf-token" />,
    "/admin/overview",
  );

  expect(await screen.findByText("New Operator")).toBeVisible();
  expect(screen.getByRole("button", { name: "Reject" })).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Rejection reason"), "Duties not confirmed.");
  await userEvent.click(screen.getByRole("button", { name: "Reject" }));

  expect(await screen.findByText("No pending access requests")).toBeVisible();
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/admin/registrations/registration-1/reject",
    expect.objectContaining({
      body: JSON.stringify({ reason: "Duties not confirmed." }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
      method: "POST",
    }),
  );
});

test("surfaces a generic decision failure", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ registrations: [pendingRegistration] }),
    })
    .mockResolvedValue({
      ok: false,
      status: 409,
      json: () => Promise.resolve({ error: { code: "username_taken", message: "Taken." } }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(
    <RegistrationApprovalsPanel csrfToken="test-csrf-token" />,
    "/admin/overview",
  );

  await userEvent.click(await screen.findByRole("button", { name: "Approve" }));

  await waitFor(() =>
    expect(
      screen.getByText("The decision could not be applied. Refresh and try again."),
    ).toBeVisible(),
  );
});

test("renders an access requests error state", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
    }),
  );

  renderWithProviders(
    <RegistrationApprovalsPanel csrfToken="test-csrf-token" />,
    "/admin/overview",
  );

  expect(
    await screen.findByText("Unable to load data", undefined, { timeout: 5000 }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
});
