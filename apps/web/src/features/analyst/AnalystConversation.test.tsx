import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AnalystConversation } from "./AnalystConversation";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("loads the complete transcript only after expansion and renders it as text", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () =>
      Promise.resolve({
        messages: [
          {
            id: "message-1",
            author: "user",
            body: '<img src="x" onerror="alert(1)">',
            createdAt: "2026-07-14T10:00:00Z",
          },
          {
            id: "message-2",
            author: "assistant",
            body: "What decision should the assessment support?",
            createdAt: "2026-07-14T10:01:00Z",
          },
        ],
      }),
  });
  vi.stubGlobal("fetch", fetchMock);

  const { container } = renderWithProviders(<AnalystConversation ticketId="ticket/one" />);
  expect(fetchMock).not.toHaveBeenCalled();

  await userEvent.click(screen.getByText("Request conversation"));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/analyst/tasks/ticket%2Fone/conversation",
      { credentials: "include", method: "GET" },
    ),
  );
  expect(await screen.findByText('<img src="x" onerror="alert(1)">')).toBeVisible();
  expect(screen.getByText("What decision should the assessment support?")).toBeVisible();
  expect(container.querySelector("img")).toBeNull();
});

test("offers a retry when the conversation request fails", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: false,
    status: 503,
    json: () => Promise.resolve({ error: { code: "unavailable", message: "Unavailable." } }),
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<AnalystConversation ticketId="ticket-1" />);
  await userEvent.click(screen.getByText("Request conversation"));
  expect(await screen.findByRole("button", { name: "Retry" })).toBeVisible();
});

test("explains when no customer conversation was recorded", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ messages: [] }) }),
  );

  renderWithProviders(<AnalystConversation ticketId="ticket-1" />);
  await userEvent.click(screen.getByText("Request conversation"));

  expect(
    await screen.findByText("No customer conversation was recorded for this request."),
  ).toBeVisible();
});
