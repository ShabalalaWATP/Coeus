import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import StoreSubscriptionsPage from "./StoreSubscriptionsPage";
import { subscriptionFixture, subscriptionScopeFixture } from "./store-organisation.fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => resetQueryClientForTests());

function requestUrl(input: RequestInfo | URL): string {
  return typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
}

test("prefills a subscription from a search and saves it privately", async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = requestUrl(input);
    const response = url.endsWith("/subscription-scopes")
      ? [subscriptionScopeFixture]
      : init?.method === "POST"
        ? subscriptionFixture
        : [];
    return Promise.resolve({ ok: true, json: () => Promise.resolve(response) });
  });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(
    <StoreSubscriptionsPage />,
    "/store/subscriptions?q=drone+activity&region=Eastern+Europe&acg=acg-eastern",
  );

  const keywords = await screen.findByLabelText(/^Keywords or phrases/);
  expect(keywords).toHaveValue("drone activity");
  await userEvent.clear(keywords);
  await userEvent.type(keywords, "drone activity");
  expect(screen.getByLabelText("Region")).toHaveValue("Eastern Europe");
  const acg = await screen.findByRole("checkbox", { name: /ACG-EAST/ });
  expect(acg).toBeChecked();
  await userEvent.click(acg);
  expect(acg).not.toBeChecked();
  await userEvent.click(acg);
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
  const request = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
  const body = request?.[1]?.body;
  expect(JSON.parse(typeof body === "string" ? body : "{}")).toMatchObject({
    criteria: { acgIds: ["acg-eastern"], query: "drone activity" },
  });
});

test("opens, pauses and deletes an existing subscription", async () => {
  let subscriptions = [subscriptionFixture];
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    if (requestUrl(input).endsWith("/subscription-scopes")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve([subscriptionScopeFixture]),
      });
    }
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
    "/store?acg=acg-eastern&q=drone+activity&region=Eastern+Europe",
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
    vi.fn((input: RequestInfo | URL) =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve(
            requestUrl(input).endsWith("/subscription-scopes") ? [subscriptionScopeFixture] : [],
          ),
      }),
    ),
  );
  renderWithProviders(<StoreSubscriptionsPage />, "/store/subscriptions");

  expect(await screen.findByText(/No subscriptions yet\./)).toBeVisible();
});

test("does not open a subscription after its selected ACG access is removed", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve(
            requestUrl(input).endsWith("/subscription-scopes") ? [] : [subscriptionFixture],
          ),
      }),
    ),
  );
  renderWithProviders(<StoreSubscriptionsPage />, "/store/subscriptions");

  expect(await screen.findByText("ACG access changed")).toBeVisible();
  expect(screen.queryByRole("link", { name: "Open results" })).not.toBeInTheDocument();
});

test("explains when the user's available ACGs cannot be loaded", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) =>
      Promise.resolve(
        requestUrl(input).endsWith("/subscription-scopes")
          ? { ok: false, status: 503, json: () => Promise.resolve({}) }
          : { ok: true, json: () => Promise.resolve([subscriptionFixture]) },
      ),
    ),
  );
  renderWithProviders(<StoreSubscriptionsPage />, "/store/subscriptions?q=ports");

  expect(
    await screen.findByText("Your available ACGs could not be loaded.", {}, { timeout: 3_000 }),
  ).toBeVisible();
  expect(screen.queryByRole("link", { name: "Open results" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Pause Regional drone reporting" })).toBeDisabled();
});
