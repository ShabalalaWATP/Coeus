import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";

import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";
import { WorkUpdatesPanel } from "./WorkUpdatesPanel";

beforeEach(resetQueryClientForTests);
afterEach(() => vi.restoreAllMocks());

test("work updates are collapsed, privacy-minimised and accessible", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve(
            url.includes("preferences")
              ? { mode: "immediate", dueReminders: true, version: 0 }
              : {
                  items: [
                    {
                      updateId: "update-1",
                      kind: "assignment",
                      unitId: "unit-1",
                      objectType: "ticket",
                      objectId: "ticket-1",
                      occurredAt: "2026-08-04T08:00:00Z",
                      acknowledgedAt: null,
                    },
                  ],
                  nextCursor: null,
                },
          ),
      }),
    ),
  );
  const view = renderWithProviders(<WorkUpdatesPanel csrfToken="csrf" />);
  expect(fetch).not.toHaveBeenCalled();
  await userEvent.click(screen.getByText("Work updates"));
  expect(await screen.findByText("Work assigned")).toBeVisible();
  expect(screen.queryByText(/ticket-1/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Mark read" })).toBeVisible();
  expect(await axe(view.container)).toHaveNoViolations();
});

test("updates can be acknowledged and preferences changed", async () => {
  const update = {
    updateId: "update-1",
    kind: "unrecognised_kind",
    unitId: "unit-1",
    objectType: "ticket",
    objectId: "ticket-1",
    occurredAt: "2026-08-04T08:00:00Z",
    acknowledgedAt: null,
  };
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (url.includes("preferences")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            mode: init?.method === "PUT" ? "digest" : "immediate",
            dueReminders: true,
            version: init?.method === "PUT" ? 1 : 0,
          }),
      });
    }
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve(
          init?.method === "POST"
            ? { ...update, acknowledgedAt: "2026-08-04T09:00:00Z" }
            : { items: [update], nextCursor: null },
        ),
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<WorkUpdatesPanel csrfToken="csrf" />);
  await userEvent.click(screen.getByText("Work updates"));
  expect(await screen.findByText("Work update")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Mark read" }));
  await userEvent.selectOptions(screen.getByLabelText("Presentation"), "digest");
  await userEvent.click(screen.getByRole("checkbox", { name: /due-date reminders/i }));
  await waitFor(() =>
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "PUT")).toHaveLength(2),
  );
});

test("empty and failed update states do not expose internal detail", async () => {
  const fetchMock = vi
    .fn()
    .mockRejectedValueOnce(new Error("updates failed"))
    .mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ mode: "immediate", dueReminders: true, version: 0 }),
    });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<WorkUpdatesPanel csrfToken="csrf" />);
  await userEvent.click(screen.getByText("Work updates"));
  expect(await screen.findByText("Work updates are not available.")).toBeVisible();
  expect(screen.queryByText(/updates failed/)).not.toBeInTheDocument();
});

test("acknowledgement failures are explained generically", async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (init?.method === "POST") return Promise.reject(new Error("write failed"));
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve(
          url.includes("preferences")
            ? { mode: "immediate", dueReminders: true, version: 0 }
            : {
                items: [
                  {
                    updateId: "update-1",
                    kind: "assignment",
                    unitId: "unit-1",
                    objectType: "ticket",
                    objectId: "ticket-1",
                    occurredAt: "2026-08-04T08:00:00Z",
                    acknowledgedAt: null,
                  },
                ],
                nextCursor: null,
              },
        ),
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<WorkUpdatesPanel csrfToken="csrf" />);
  await userEvent.click(screen.getByText("Work updates"));
  await userEvent.click(await screen.findByRole("button", { name: "Mark read" }));
  expect(await screen.findByText("The update could not be saved.")).toBeVisible();
});

test("read and empty inbox states are rendered", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve(
            url.includes("preferences")
              ? { mode: "digest", dueReminders: false, version: 2 }
              : {
                  items: [
                    {
                      updateId: "update-2",
                      kind: "returned",
                      unitId: "unit-1",
                      objectType: "ticket",
                      objectId: "ticket-2",
                      occurredAt: "2026-08-04T08:00:00Z",
                      acknowledgedAt: "2026-08-04T09:00:00Z",
                    },
                  ],
                  nextCursor: null,
                },
          ),
      });
    }),
  );
  renderWithProviders(<WorkUpdatesPanel csrfToken="csrf" />);
  await userEvent.click(screen.getByText("Work updates"));
  expect(await screen.findByText("Read")).toBeVisible();
  expect(screen.getByText("Work was returned")).toBeVisible();
});

test("an empty current inbox is explained", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve(
            url.includes("preferences")
              ? { mode: "immediate", dueReminders: true, version: 0 }
              : { items: [], nextCursor: null },
          ),
      });
    }),
  );
  renderWithProviders(<WorkUpdatesPanel csrfToken="csrf" />);
  await userEvent.click(screen.getByText("Work updates"));
  expect(await screen.findByText("No current updates.")).toBeVisible();
});
