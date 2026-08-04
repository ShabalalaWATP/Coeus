import { screen } from "@testing-library/react";

import { TeamCapacitySummary } from "./TeamCapacitySummary";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(resetQueryClientForTests);
afterEach(() => vi.restoreAllMocks());

test("explains a partial advisory forecast in plain language", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          status: "partial",
          peopleIncluded: 3,
          physicalMinutes: 7_200,
          assignableMinutes: 6_360,
          reservationMinutes: 240,
        }),
    }),
  );

  renderWithProviders(<TeamCapacitySummary grantId="grant-1" unitId="unit-1" />);

  expect(await screen.findByText("106 hours")).toBeVisible();
  expect(screen.getByText(/forecast is incomplete/)).toBeVisible();
  expect(fetch).toHaveBeenCalledWith(
    expect.stringContaining("authorisingGrantId=grant-1"),
    expect.objectContaining({ method: "GET" }),
  );
});

test("does not imply availability when evidence is unknown", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: "unknown" }),
    }),
  );

  renderWithProviders(<TeamCapacitySummary grantId="grant-1" unitId="unit-1" />);

  expect(await screen.findByText(/cannot be calculated/)).toBeVisible();
  expect(screen.queryByText(/hours/)).not.toBeInTheDocument();
});

test("keeps assignment checks explicit when the forecast request fails", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: () => Promise.resolve({ error: { code: "unavailable", message: "No." } }),
    }),
  );

  renderWithProviders(<TeamCapacitySummary grantId="grant-1" unitId="unit-1" />);

  expect(await screen.findByRole("status")).toHaveTextContent("Assignment checks still apply");
});
