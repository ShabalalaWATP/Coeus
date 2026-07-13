import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { resetQueryClientForTests } from "../../app/query-client";
import { baseProduct, fetchByUrl, jsonResponse, renderQcRoutes } from "./qc-test-fixtures";

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("claims an available summary before showing detail and can release it", async () => {
  const queueItems = [
    {
      ticketId: "ticket-1",
      reference: "TCK-0001",
      state: "QC_REVIEW" as const,
      claimStatus: "available" as const,
    },
  ];
  const fetchMock = vi.fn(fetchByUrl({ queueItems, queueProducts: [] }));
  vi.stubGlobal("fetch", fetchMock);

  renderQcRoutes("/qc/queue");

  expect(screen.queryByText("MOCK DATA ONLY assessment content.")).not.toBeInTheDocument();
  await userEvent.click(await screen.findByRole("button", { name: /TCK-0001/ }));
  expect(await screen.findByText("MOCK DATA ONLY assessment content.")).toBeVisible();
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/qc/products/ticket-1/claim",
    {
      credentials: "include",
      headers: { "X-CSRF-Token": "test-csrf-token" },
      method: "POST",
    },
  );

  await userEvent.click(screen.getByRole("button", { name: "Release claim" }));
  await waitFor(() => expect(screen.getByText("No QC product selected.")).toBeInTheDocument());
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/qc/products/ticket-1/claim",
    {
      credentials: "include",
      headers: { "X-CSRF-Token": "test-csrf-token" },
      method: "DELETE",
    },
  );
});

test("shows another reviewer's claim without exposing product detail", async () => {
  const fetchMock = vi.fn(
    fetchByUrl({
      queueItems: [
        {
          ticketId: "ticket-1",
          reference: "TCK-0001",
          state: "QC_REVIEW",
          claimStatus: "claimed",
        },
      ],
      queueProducts: [],
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  renderQcRoutes("/qc/queue");

  expect(await screen.findByText("Claimed by another reviewer")).toBeVisible();
  expect(screen.queryByRole("link", { name: /TCK-0001/ })).not.toBeInTheDocument();
  expect(screen.queryByText("Arctic QC product")).not.toBeInTheDocument();
});

test("shows a safe error when a claim fails", async () => {
  const fallback = fetchByUrl({
    queueItems: [
      {
        ticketId: "ticket-1",
        reference: "TCK-0001",
        state: "QC_REVIEW",
        claimStatus: "available",
      },
    ],
    queueProducts: [],
  });
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) =>
      url.endsWith("/claim") && init?.method === "POST"
        ? Promise.resolve({
            ok: false,
            status: 409,
            json: () =>
              Promise.resolve({
                error: { code: "qc_already_claimed", message: "Another reviewer claimed it." },
              }),
          })
        : fallback(url),
    ),
  );

  renderQcRoutes("/qc/queue");
  await userEvent.click(await screen.findByRole("button", { name: /TCK-0001/ }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Another reviewer claimed it.");
});

test("keeps the assigned product visible when claim release fails", async () => {
  const fallback = fetchByUrl({});
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) =>
      url.endsWith("/claim") && init?.method === "DELETE"
        ? Promise.resolve({
            ok: false,
            status: 409,
            json: () =>
              Promise.resolve({ error: { code: "ticket_changed", message: "Refresh first." } }),
          })
        : fallback(url),
    ),
  );

  renderQcRoutes("/qc/queue");
  await userEvent.click(await screen.findByRole("button", { name: "Release claim" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Refresh first.");
  expect(screen.getByText("MOCK DATA ONLY assessment content.")).toBeVisible();
});

test("disables other queue navigation while a claim is pending", async () => {
  let finishClaim!: (value: ReturnType<typeof jsonResponse>) => void;
  const fallback = fetchByUrl({
    queueItems: [
      {
        ticketId: "ticket-1",
        reference: "TCK-0001",
        state: "QC_REVIEW",
        claimStatus: "claimed_by_you",
      },
      {
        ticketId: "ticket-2",
        reference: "TCK-0002",
        state: "QC_REVIEW",
        claimStatus: "available",
      },
    ],
  });
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) =>
      url.includes("ticket-2/claim") && init?.method === "POST"
        ? new Promise<ReturnType<typeof jsonResponse>>((resolve) => {
            finishClaim = resolve;
          })
        : fallback(url),
    ),
  );

  renderQcRoutes("/qc/queue");
  const assigned = await screen.findByRole("link", { name: /TCK-0001/ });
  await userEvent.click(screen.getByRole("button", { name: /TCK-0002/ }));
  expect(assigned).toHaveAttribute("aria-disabled", "true");
  await userEvent.click(assigned);
  expect(screen.getByText("MOCK DATA ONLY assessment content.")).toBeVisible();
  finishClaim(jsonResponse({ ...baseProduct, ticketId: "ticket-2", reference: "TCK-0002" }));
  expect(await screen.findByRole("link", { name: /TCK-0002/ })).toBeVisible();
});
