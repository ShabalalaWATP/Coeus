import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { resetQueryClientForTests } from "../../app/query-client";
import type { Ticket } from "../../lib/api-client/tickets";
import { baseTicket, renderRequests } from "../../test/requests-fixtures";

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("accepts a released product from the dashboard", async () => {
  const readyTicket: Ticket = { ...baseTicket, state: "DISSEMINATION_READY" };
  const closedTicket: Ticket = { ...readyTicket, state: "CLOSED_REQUIREMENT_MET" };
  const fetchMock = vi.fn((url: string) => {
    if (url.includes("/requirement-decision")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(closedTicket) });
    }
    if (url.includes("/api/v1/tickets")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ tickets: [readyTicket] }) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderRequests("/app/requests");
  await userEvent.click(await screen.findByRole("button", { name: "Yes, close request" }));

  expect(await screen.findByText("Closed requirement met")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Yes, close request" })).not.toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/tickets/ticket-1/requirement-decision",
    expect.objectContaining({
      body: JSON.stringify({
        meetsRequirement: true,
        reason: "The released product meets the requirement.",
        unmetCriteria: [],
      }),
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": "test-csrf-token",
      },
      method: "POST",
    }),
  );
});

test("shows a dismissible error when product acceptance fails", async () => {
  const readyTicket: Ticket = { ...baseTicket, state: "DISSEMINATION_READY" };
  const fetchMock = vi.fn((url: string) => {
    if (url.includes("/requirement-decision")) {
      return Promise.resolve({
        ok: false,
        status: 409,
        json: () =>
          Promise.resolve({ error: { code: "invalid_state", message: "Not ready to close." } }),
      });
    }
    if (url.includes("/api/v1/tickets")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ tickets: [readyTicket] }) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderRequests("/app/requests");
  await userEvent.click(await screen.findByRole("button", { name: "Yes, close request" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Not ready to close.");
  await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("clears a product-decision error after a successful retry", async () => {
  const readyTicket: Ticket = { ...baseTicket, state: "DISSEMINATION_READY" };
  const closedTicket: Ticket = { ...readyTicket, state: "CLOSED_REQUIREMENT_MET" };
  const fetchMock = vi.fn((url: string) => {
    if (url.includes("/requirement-decision")) {
      const confirmationCalls = fetchMock.mock.calls.filter(([calledUrl]) =>
        String(calledUrl).includes("/requirement-decision"),
      );
      if (confirmationCalls.length === 1) {
        return Promise.resolve({
          ok: false,
          status: 409,
          json: () =>
            Promise.resolve({ error: { code: "invalid_state", message: "Not ready to close." } }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve(closedTicket) });
    }
    if (url.includes("/api/v1/tickets")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ tickets: [readyTicket] }) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderRequests("/app/requests");
  const confirm = await screen.findByRole("button", { name: "Yes, close request" });
  await userEvent.click(confirm);
  expect(await screen.findByRole("alert")).toHaveTextContent("Not ready to close.");

  await userEvent.click(confirm);

  expect(await screen.findByText("Closed requirement met")).toBeVisible();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
