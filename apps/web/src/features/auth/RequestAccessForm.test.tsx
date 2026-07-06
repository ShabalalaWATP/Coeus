import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { RequestAccessForm } from "./RequestAccessForm";

afterEach(() => {
  vi.restoreAllMocks();
});

async function fillValidRequest() {
  await userEvent.type(screen.getByLabelText("Display name"), "New Operator");
  await userEvent.type(screen.getByLabelText("Email"), "new.operator@example.test");
  await userEvent.type(screen.getByLabelText("Password"), "NewOperator1!x");
  await userEvent.type(
    screen.getByLabelText("Justification (optional)"),
    "Mock regional reporting duties.",
  );
}

test("submits an access request and confirms review", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ status: "pending" }),
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<RequestAccessForm />);

  await fillValidRequest();
  await userEvent.click(screen.getByRole("button", { name: "Submit request" }));

  expect(await screen.findByText("Request submitted.")).toBeVisible();
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("http://127.0.0.1:8001/api/v1/auth/register");
  expect(init.method).toBe("POST");
  expect(init.credentials).toBe("include");
  expect(JSON.parse(init.body as string)).toEqual({
    displayName: "New Operator",
    username: "new.operator@example.test",
    password: "NewOperator1!x",
    justification: "Mock regional reporting duties.",
  });
});

test("shows validation messages before submitting", async () => {
  vi.stubGlobal("fetch", vi.fn());
  render(<RequestAccessForm />);

  await userEvent.type(screen.getByLabelText("Password"), "short");
  await userEvent.click(screen.getByRole("button", { name: "Submit request" }));

  expect(await screen.findByText("Enter your display name.")).toBeVisible();
  expect(screen.getByText("Enter a valid email address.")).toBeVisible();
  expect(screen.getByText("Use at least 12 characters.")).toBeVisible();
});

test("explains registration throttling without leaking detail", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: () =>
        Promise.resolve({ error: { code: "registration_throttled", message: "Too many." } }),
    }),
  );
  render(<RequestAccessForm />);

  await fillValidRequest();
  await userEvent.click(screen.getByRole("button", { name: "Submit request" }));

  expect(
    await screen.findByText("Too many pending requests right now. Try again later."),
  ).toBeVisible();
});

test("shows a generic message for other submission failures", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: () => Promise.resolve({ error: { code: "validation_error", message: "Bad." } }),
    }),
  );
  render(<RequestAccessForm />);

  await fillValidRequest();
  await userEvent.click(screen.getByRole("button", { name: "Submit request" }));

  await waitFor(() =>
    expect(
      screen.getByText("The request could not be submitted. Check the form and try again."),
    ).toBeVisible(),
  );
});
