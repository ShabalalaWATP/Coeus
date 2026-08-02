import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import StoreSubscriptionsPage from "./StoreSubscriptionsPage";
import { subscriptionFixture } from "./store-organisation.fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => resetQueryClientForTests());

test("prefills a subscription from a search and saves it privately", async () => {
  const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve(init?.method === "POST" ? subscriptionFixture : []),
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(
    <StoreSubscriptionsPage />,
    "/store/subscriptions?query=drone+activity&region=Eastern+Europe",
  );

  expect(await screen.findByLabelText("Search terms")).toHaveValue("drone activity");
  expect(screen.getByLabelText("Region")).toHaveValue("Eastern Europe");
  await userEvent.type(screen.getByLabelText("Name"), "Regional drone reporting");
  await userEvent.selectOptions(screen.getByLabelText("Review cadence"), "daily");
  await userEvent.type(screen.getByLabelText("Product type"), "assessment_report");
  await userEvent.type(screen.getByLabelText("Tag"), "aviation");
  await userEvent.type(screen.getByLabelText("Source type"), "finished_assessment");
  await userEvent.type(screen.getByLabelText("Coverage from"), "2026-01-01");
  await userEvent.type(screen.getByLabelText("Coverage to"), "2026-08-02");
  await userEvent.click(screen.getByRole("button", { name: "Create subscription" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/store/subscriptions",
      expect.objectContaining({ method: "POST" }),
    ),
  );
});

test("opens, pauses and deletes an existing subscription", async () => {
  let subscriptions = [subscriptionFixture];
  const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === "PUT") {
      subscriptions = [{ ...subscriptionFixture, enabled: false }];
      return Promise.resolve({ ok: true, json: () => Promise.resolve(subscriptions[0]) });
    }
    if (init?.method === "DELETE") {
      subscriptions = [];
      return Promise.resolve({ ok: true });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(subscriptions) });
  });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<StoreSubscriptionsPage />, "/store/subscriptions");

  expect(await screen.findByRole("link", { name: "Open results" })).toHaveAttribute(
    "href",
    "/store?query=drone+activity&region=Eastern+Europe",
  );
  await userEvent.click(screen.getByRole("button", { name: "Pause Regional drone reporting" }));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Resume Regional drone reporting" })).toBeVisible(),
  );
  await userEvent.click(screen.getByRole("button", { name: "Delete Regional drone reporting" }));
  await waitFor(() =>
    expect(screen.queryByText("Regional drone reporting")).not.toBeInTheDocument(),
  );
});

test("shows a clear empty subscription state", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve([]) })),
  );
  renderWithProviders(<StoreSubscriptionsPage />, "/store/subscriptions");

  expect(await screen.findByText(/No subscriptions yet\./)).toBeVisible();
});
