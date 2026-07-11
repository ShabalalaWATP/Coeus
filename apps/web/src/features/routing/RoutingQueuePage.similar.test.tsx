import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import RoutingQueuePage from "./RoutingQueuePage";
import { jsonResponse, queueWith, reviewedTicket } from "./routing-test-fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const similarList = {
  matches: [
    {
      ticketId: "related-1",
      reference: "TCK-0002",
      title: "Arctic maritime overlap",
      state: "JIOC_REVIEW",
      score: 0.68,
      reasons: ["similarity:lexical-rank:1", "similarity:metadata-region"],
      alreadyLinked: false,
    },
  ],
};

const linkedList = {
  matches: [{ ...similarList.matches[0], alreadyLinked: true }],
};

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("shows manager similar open requests and links a related ticket", async () => {
  const fetchMock = routingSimilarFetch();
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<RoutingQueuePage queue="jioc" />, "/rfa/queue");

  expect(await screen.findByText("Similar open requests")).toBeVisible();
  expect(await screen.findByText("TCK-0002")).toBeVisible();
  await userEvent.click(await screen.findByRole("button", { name: "Link as related" }));

  expect(await screen.findByRole("button", { name: "Linked" })).toBeDisabled();
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/similar-requests/routing/ticket-1/link/related-1",
    expect.objectContaining({
      headers: { "X-CSRF-Token": "test-csrf-token" },
      method: "POST",
    }),
  );
});

test("surfaces manager link failures inline", async () => {
  vi.stubGlobal("fetch", routingSimilarFetch({ linkFails: true }));

  renderWithProviders(<RoutingQueuePage queue="jioc" />, "/rfa/queue");

  await userEvent.click(await screen.findByRole("button", { name: "Link as related" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Link failed.");
});

function routingSimilarFetch(options: { linkFails?: boolean } = {}) {
  return vi.fn((url: string) => {
    if (url.includes("capability-catalogue")) {
      return Promise.resolve(jsonResponse({ teams: [] }));
    }
    if (url.includes("/similar-requests/routing/ticket-1/link/related-1")) {
      return Promise.resolve(
        options.linkFails
          ? {
              ok: false,
              status: 500,
              json: () =>
                Promise.resolve({ error: { code: "link_failed", message: "Link failed." } }),
            }
          : jsonResponse(linkedList),
      );
    }
    if (url.includes("/similar-requests/routing/ticket-1")) {
      return Promise.resolve(jsonResponse(similarList));
    }
    if (url.includes("/routing/jioc/queue")) {
      return Promise.resolve(jsonResponse(queueWith([reviewedTicket])));
    }
    return Promise.resolve(jsonResponse({}));
  });
}
