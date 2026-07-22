import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ChangePasswordPage from "./ChangePasswordPage";
import { resetQueryClientForTests } from "../../app/query-client";
import { previewSession, renderWithProviders } from "../../test/test-utils";

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

const VALID_PASSWORD = "NewPassword123!";

async function fillForm(newPassword = VALID_PASSWORD, confirm = newPassword) {
  await userEvent.type(screen.getByLabelText("Current password"), "OldPassword123!");
  await userEvent.type(screen.getByLabelText("New password"), newPassword);
  await userEvent.type(screen.getByLabelText("Confirm new password"), confirm);
}

test("keeps the submit disabled and hints while the form is invalid", async () => {
  renderWithProviders(<ChangePasswordPage />, "/account/password");

  const submit = screen.getByRole("button", { name: "Change password" });
  expect(submit).toBeDisabled();

  await userEvent.type(screen.getByLabelText("Current password"), "OldPassword123!");
  await userEvent.type(screen.getByLabelText("New password"), "short");
  expect(screen.getByText("The new password needs at least 12 characters.")).toBeVisible();
  expect(submit).toBeDisabled();

  await userEvent.clear(screen.getByLabelText("New password"));
  await userEvent.type(screen.getByLabelText("New password"), VALID_PASSWORD);
  await userEvent.type(screen.getByLabelText("Confirm new password"), "Different123!");
  expect(screen.getByText("The passwords do not match.")).toBeVisible();
  expect(submit).toBeDisabled();
});

test("changes the password and adopts the rotated session", async () => {
  const fetchMock = vi.fn().mockResolvedValueOnce({
    ok: true,
    json: () =>
      Promise.resolve({
        ...previewSession,
        csrfToken: "rotated-csrf-token",
        user: { ...previewSession.user, passwordResetRequired: false },
      }),
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<ChangePasswordPage />, "/account/password");

  await fillForm();
  await userEvent.click(screen.getByRole("button", { name: "Change password" }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  expect(fetchMock).toHaveBeenNthCalledWith(
    1,
    "http://127.0.0.1:8001/api/v1/auth/password",
    expect.objectContaining({
      body: JSON.stringify({
        currentPassword: "OldPassword123!",
        newPassword: VALID_PASSWORD,
      }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
      method: "POST",
    }),
  );
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("shows a clear message when the current password is wrong", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: () =>
        Promise.resolve({ error: { code: "invalid_credentials", message: "Wrong password." } }),
    }),
  );

  renderWithProviders(<ChangePasswordPage />, "/account/password");

  await fillForm();
  await userEvent.click(screen.getByRole("button", { name: "Change password" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("The current password is incorrect.");
});

test("surfaces policy violations from the API error body", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: () =>
        Promise.resolve({
          error: { code: "password_policy", message: "Passwords need 12 or more characters." },
        }),
    }),
  );

  renderWithProviders(<ChangePasswordPage />, "/account/password");

  await fillForm();
  await userEvent.click(screen.getByRole("button", { name: "Change password" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Passwords need 12 or more characters.",
  );
});

test("shows a generic message for unexpected failures", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.reject(new Error("no body")),
    }),
  );

  renderWithProviders(<ChangePasswordPage />, "/account/password");

  await fillForm();
  await userEvent.click(screen.getByRole("button", { name: "Change password" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The password could not be changed. Try again.",
  );
});

test("explains the forced flow when a reset is required", () => {
  renderWithProviders(<ChangePasswordPage />, "/account/password", {
    ...previewSession,
    user: { ...previewSession.user, passwordResetRequired: true },
  });

  expect(
    screen.getByText("You must change your password before you can continue using Istari."),
  ).toBeVisible();
});
