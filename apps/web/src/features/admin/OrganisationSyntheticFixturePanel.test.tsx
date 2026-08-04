import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { OrganisationSyntheticFixturePanel } from "./OrganisationSyntheticFixturePanel";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const creates = {
  units: 25,
  deliveryProfiles: 7,
  memberships: 54,
  workingPatterns: 24,
  grants: 107,
  teamCapabilities: 61,
  competencies: 48,
  calendarEvents: 8,
  tasks: 24,
  taskOwnership: 24,
  workPackages: 48,
  capacityReservations: 2,
  total: 432,
};

const empty = {
  units: 0,
  deliveryProfiles: 0,
  memberships: 0,
  workingPatterns: 0,
  grants: 0,
  teamCapabilities: 0,
  competencies: 0,
  calendarEvents: 0,
  tasks: 0,
  taskOwnership: 0,
  workPackages: 0,
  capacityReservations: 0,
  total: 0,
};

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("previews and applies the exact additive fixture after password confirmation", async () => {
  const requests: { url: string; init?: RequestInit }[] = [];
  let applied = false;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      requests.push({ url, init });
      if (url.endsWith("/synthetic-fixture-commands")) {
        applied = true;
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              commandId: "00000000-0000-4000-8000-000000000001",
              manifestVersion: "synthetic-organisation-v2",
              created: creates,
              replayed: false,
            }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            manifestVersion: "synthetic-organisation-v2",
            previewHash: "a".repeat(64),
            canApply: true,
            creates: applied ? empty : creates,
            unchanged: applied ? creates : empty,
            findings: [],
          }),
      });
    }),
  );

  renderWithProviders(<OrganisationSyntheticFixturePanel onClose={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: "Check exercise data" }));
  expect(await screen.findByRole("heading", { name: "Ready to build" })).toBeVisible();
  expect(screen.getByText("54")).toBeVisible();
  await userEvent.type(screen.getByLabelText("Current password"), "current-password");
  await userEvent.click(screen.getByRole("button", { name: "Build exercise organisation" }));
  expect(await screen.findByText("Exercise organisation is up to date.")).toBeVisible();

  const applyRequest = requests.find((item) => item.url.endsWith("/synthetic-fixture-commands"));
  const rawBody = applyRequest?.init?.body;
  expect(typeof rawBody).toBe("string");
  const body = JSON.parse(typeof rawBody === "string" ? rawBody : "{}") as Record<string, unknown>;
  expect(body.previewHash).toBe("a".repeat(64));
  expect(body.currentPassword).toBe("current-password");
  expect(body).not.toHaveProperty("actorUserId");
  expect(new Headers(applyRequest?.init?.headers).get("X-CSRF-Token")).toBe("test-csrf-token");
  expect(screen.queryByDisplayValue("current-password")).not.toBeInTheDocument();
});

test("shows conflicts without exposing an apply control", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            manifestVersion: "synthetic-organisation-v2",
            previewHash: "b".repeat(64),
            canApply: false,
            creates,
            unchanged: empty,
            findings: [
              {
                code: "foreign_root",
                entityType: "unit",
                entityKey: "di",
                message: "A different active root exists.",
              },
            ],
          }),
      }),
    ),
  );

  renderWithProviders(<OrganisationSyntheticFixturePanel onClose={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: "Check exercise data" }));
  expect(await screen.findByRole("heading", { name: "Review required" })).toBeVisible();
  expect(screen.getByText(/different active root/i)).toBeVisible();
  expect(screen.queryByLabelText("Current password")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: /Build exercise organisation/ }),
  ).not.toBeInTheDocument();
  await waitFor(() => expect(screen.getByText(/Unsafe conflicts are report-only/)).toBeVisible());
});

test("offers exact fixture drift reconciliation after password confirmation", async () => {
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      urls.push(url);
      if (url.endsWith("/synthetic-fixture-reconcile-commands")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              commandId: "00000000-0000-4000-8000-000000000002",
              manifestVersion: "synthetic-organisation-v2",
              created: empty,
              replayed: false,
              reconciledRows: 1,
            }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            manifestVersion: "synthetic-organisation-v2",
            previewHash: "d".repeat(64),
            canApply: false,
            creates: empty,
            unchanged: creates,
            findings: [
              {
                code: "fixture_row_changed",
                entityType: "unit",
                entityKey: "di",
                message: "Existing synthetic row differs from the manifest.",
              },
            ],
          }),
      });
    }),
  );
  renderWithProviders(<OrganisationSyntheticFixturePanel onClose={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: "Check exercise data" }));
  await userEvent.type(screen.getByLabelText("Current password"), "current-password");
  await userEvent.click(screen.getByRole("button", { name: "Restore reviewed exercise data" }));
  await waitFor(() =>
    expect(urls.some((url) => url.endsWith("/synthetic-fixture-reconcile-commands"))).toBe(true),
  );
});

test("supports closing and reports a failed unauthenticated preview", async () => {
  let rejectPreview: (reason: Error) => void = () => undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn(
      () =>
        new Promise<Response>((_resolve, reject) => {
          rejectPreview = reject;
        }),
    ),
  );
  const close = vi.fn();
  renderWithProviders(<OrganisationSyntheticFixturePanel onClose={close} />, "/admin", null);
  await userEvent.click(screen.getByRole("button", { name: "Close exercise data" }));
  expect(close).toHaveBeenCalledTimes(1);
  await userEvent.click(screen.getByRole("button", { name: "Check exercise data" }));
  expect(screen.getByRole("button", { name: "Checking exercise data…" })).toBeDisabled();
  rejectPreview(new Error("preview unavailable"));
  expect(await screen.findByRole("alert")).toHaveTextContent("preview unavailable");
});

test("reports an apply failure and restores the apply action", async () => {
  let request = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(() => {
      request += 1;
      if (request === 1) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              manifestVersion: "synthetic-organisation-v2",
              previewHash: "c".repeat(64),
              canApply: true,
              creates,
              unchanged: empty,
              findings: [],
            }),
        });
      }
      return Promise.reject(new Error("apply unavailable"));
    }),
  );
  renderWithProviders(<OrganisationSyntheticFixturePanel onClose={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: "Check exercise data" }));
  await screen.findByRole("heading", { name: "Ready to build" });
  await userEvent.type(screen.getByLabelText("Current password"), "current-password");
  await userEvent.click(screen.getByRole("button", { name: "Build exercise organisation" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("apply unavailable");
  expect(screen.getByRole("button", { name: "Build exercise organisation" })).toBeEnabled();
});
