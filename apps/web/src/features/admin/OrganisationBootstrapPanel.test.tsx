import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { OrganisationBootstrapPanel } from "./OrganisationBootstrapPanel";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("submits the trimmed one-time ceremony and clears protected fields", async () => {
  let resolveRequest: (response: Response) => void = () => undefined;
  const fetchMock = vi.fn(
    (url: string, init?: RequestInit) =>
      new Promise<Response>((resolve) => {
        void url;
        void init;
        resolveRequest = resolve;
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
  const close = vi.fn();
  renderWithProviders(<OrganisationBootstrapPanel onClose={close} />, "/admin");

  await userEvent.type(screen.getByLabelText("Root name"), "  Exercise Command  ");
  await userEvent.type(screen.getByLabelText("Short name"), "  EXC  ");
  await userEvent.clear(screen.getByLabelText("Time zone"));
  await userEvent.type(screen.getByLabelText("Time zone"), "  Europe/London  ");
  await userEvent.type(screen.getByLabelText("Description"), "  Exercise hierarchy  ");
  await userEvent.type(screen.getByLabelText("Current password"), "current-password");
  await userEvent.type(screen.getByLabelText("Setup code"), "x".repeat(32));
  await userEvent.click(screen.getByRole("button", { name: "Create organisation root" }));
  expect(screen.getByRole("button", { name: "Creating root…" })).toBeDisabled();

  resolveRequest(
    new Response(
      JSON.stringify({
        rootUnitId: "00000000-0000-4000-8000-000000000001",
        topologyRevisionId: "00000000-0000-4000-8000-000000000002",
        grantIds: [],
        replayed: false,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );
  await waitFor(() => expect(close).toHaveBeenCalledTimes(1));

  const rawBody = fetchMock.mock.calls[0]?.[1]?.body;
  expect(typeof rawBody).toBe("string");
  const body = JSON.parse(typeof rawBody === "string" ? rawBody : "{}") as Record<string, unknown>;
  expect(body).toMatchObject({
    rootName: "Exercise Command",
    rootShortName: "EXC",
    timeZone: "Europe/London",
    description: "Exercise hierarchy",
    currentPassword: "current-password",
    setupNonce: "x".repeat(32),
  });
});

test("can close without submitting and reports a rejected ceremony", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.reject(new Error("setup unavailable"))),
  );
  const close = vi.fn();
  renderWithProviders(<OrganisationBootstrapPanel onClose={close} />, "/admin", null);
  await userEvent.click(screen.getByRole("button", { name: "Close organisation setup" }));
  expect(close).toHaveBeenCalledTimes(1);
  await userEvent.type(screen.getByLabelText("Root name"), "Exercise Command");
  await userEvent.type(screen.getByLabelText("Short name"), "EXC");
  await userEvent.type(screen.getByLabelText("Current password"), "current-password");
  await userEvent.type(screen.getByLabelText("Setup code"), "x".repeat(32));
  await userEvent.click(screen.getByRole("button", { name: "Create organisation root" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("setup unavailable");
});
