import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { OrganisationCutoverReadinessPanel } from "./OrganisationCutoverReadinessPanel";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const passedCheck = {
  code: "migration_head",
  status: "passed",
  observedCount: 1,
  requiredCount: 1,
};

const blockedCheck = {
  code: "browser_evidence",
  status: "blocked",
  observedCount: 0,
  requiredCount: 1,
};

const errorCheck = {
  code: "security_evidence",
  status: "error",
  observedCount: 0,
  requiredCount: 1,
};

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("separates blockers from passed checks and keeps technical details collapsed", async () => {
  let resolveResponse: ((value: unknown) => void) | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn(
      () =>
        new Promise((resolve) => {
          resolveResponse = resolve;
        }),
    ),
  );

  renderWithProviders(<OrganisationCutoverReadinessPanel />);
  expect(screen.getByText(/checking whether the organisation is ready/i)).toBeVisible();

  resolveResponse?.({
    ok: true,
    json: () => Promise.resolve({ ready: false, checks: [passedCheck, blockedCheck, errorCheck] }),
  });

  expect(
    await screen.findByRole("heading", { name: "Not ready to change services" }),
  ).toBeVisible();
  expect(screen.getByRole("heading", { name: "What needs attention" })).toBeVisible();
  expect(screen.getByText("User journeys have been checked")).toBeVisible();
  expect(screen.getByText("Security checks have passed")).toBeVisible();
  expect(screen.getByText(/could not be verified/i)).toBeVisible();
  expect(screen.getByText("migration_head")).not.toBeVisible();
  expect(screen.getByText("Passed").nextElementSibling).toHaveTextContent("1");
  expect(screen.getByText("Need attention").nextElementSibling).toHaveTextContent("2");

  await userEvent.click(screen.getByText("Technical details"));
  expect(screen.getByText("migration_head")).toBeVisible();
});

test("shows a plain-language ready result without change controls", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ ready: true, checks: [passedCheck] }),
      }),
    ),
  );

  renderWithProviders(<OrganisationCutoverReadinessPanel />);

  expect(
    await screen.findByRole("heading", { name: "Ready for a controlled service change" }),
  ).toBeVisible();
  expect(screen.getByText(/does not make or approve a change/i)).toBeVisible();
  expect(screen.queryByRole("heading", { name: "What needs attention" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

test("handles an empty result and checks again", async () => {
  let calls = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(() => {
      calls += 1;
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve(
            calls === 1 ? { ready: false, checks: [] } : { ready: true, checks: [passedCheck] },
          ),
      });
    }),
  );

  renderWithProviders(<OrganisationCutoverReadinessPanel />);
  expect(
    await screen.findByRole("heading", { name: "No readiness checks were returned" }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Check again" }));

  expect(
    await screen.findByRole("heading", { name: "Ready for a controlled service change" }),
  ).toBeVisible();
});

test("explains a failed check and offers a working retry", async () => {
  let calls = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(() => {
      calls += 1;
      if (calls === 1) {
        return Promise.resolve({
          ok: false,
          status: 503,
          json: () => Promise.resolve({ error: { code: "unavailable", message: "Unavailable" } }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ ready: true, checks: [passedCheck] }),
      });
    }),
  );

  renderWithProviders(<OrganisationCutoverReadinessPanel />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Retry readiness check" }, { timeout: 4_000 }),
  );

  await waitFor(() =>
    expect(
      screen.getByRole("heading", { name: "Ready for a controlled service change" }),
    ).toBeVisible(),
  );
});
