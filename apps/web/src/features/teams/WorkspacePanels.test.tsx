import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { WorkspaceCapabilitiesPanel } from "./WorkspaceCapabilitiesPanel";
import { WorkspaceOverviewPanel } from "./WorkspaceOverviewPanel";
import { WorkspacePeoplePanel } from "./WorkspacePeoplePanel";
import { failure, ok, person, stub } from "./workspace-panels.fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(resetQueryClientForTests);
afterEach(() => vi.restoreAllMocks());
test("overview states its scope and freshness and downloads an authorised export", async () => {
  const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  vi.stubGlobal("URL", {
    ...URL,
    createObjectURL: vi.fn(() => "blob:export"),
    revokeObjectURL: vi.fn(),
  });
  const fetchMock = stub((url) => {
    if (url.includes("/analytics")) {
      return ok({
        unitId: "unit-1",
        scope: "descendants",
        generatedAt: "2026-08-03T12:00:00Z",
        metrics: [
          {
            key: "load",
            label: "Load",
            value: 3,
            display: "3",
            scope: "descendants",
            period: "7 days",
          },
        ],
        privacyNotice: "Small cohorts are suppressed.",
      });
    }
    if (url.includes("/exports/")) return ok({});
    if (url.includes("/exports")) return ok({ exportId: "export-1" });
    return ok({
      unitId: "unit-1",
      scope: "descendants",
      generatedAt: "2026-08-03T12:00:00Z",
      freshUntil: "2026-08-03T12:15:00Z",
      metrics: [
        {
          key: "headcount",
          label: "Headcount",
          value: 8,
          display: "8",
          scope: "descendants",
          period: "current",
        },
      ],
      truncatedCount: 0,
      suppressed: true,
    });
  });

  renderWithProviders(
    <WorkspaceOverviewPanel
      csrfToken="csrf"
      exportGrant={{ id: "grant-1", version: 2 }}
      includeDescendants
      unitId="unit-1"
    />,
  );

  expect(await screen.findByRole("heading", { name: "Operational overview" })).toBeVisible();
  expect(screen.getByText(/Direct and child-team scope/)).toBeVisible();
  expect(screen.getByText(/shown as fewer than five/)).toBeVisible();
  expect(await screen.findByText("Small cohorts are suppressed.")).toBeVisible();

  await userEvent.click(screen.getByRole("button", { name: /Export operational summary/ }));

  await waitFor(() => expect(anchorClick).toHaveBeenCalled());
  const requested = fetchMock.mock.calls.map(([url]) => String(url));
  expect(requested.some((url) => url.includes("/exports/export-1/download"))).toBe(true);
});

test("overview reports a refused export without losing the metrics", async () => {
  stub((url) => {
    if (url.includes("/exports")) return failure(409);
    if (url.includes("/analytics")) return failure(403);
    return ok({
      unitId: "unit-1",
      scope: "direct",
      generatedAt: "2026-08-03T12:00:00Z",
      freshUntil: "2026-08-03T12:15:00Z",
      metrics: [
        {
          key: "headcount",
          label: "Headcount",
          value: 8,
          display: "8",
          scope: "direct",
          period: "current",
        },
      ],
      truncatedCount: 0,
      suppressed: false,
    });
  });

  renderWithProviders(
    <WorkspaceOverviewPanel
      csrfToken="csrf"
      exportGrant={{ id: "grant-1", version: 2 }}
      includeDescendants={false}
      unitId="unit-1"
    />,
  );

  await userEvent.click(await screen.findByRole("button", { name: /Export operational summary/ }));

  expect(await screen.findByRole("alert")).toHaveTextContent("The export could not be prepared.");
  expect(screen.getByText("Headcount")).toBeVisible();
  expect(screen.getByText(/Every measure states its period and scope./)).toBeVisible();
  // A refused analytics read must not invent planning signals.
  expect(screen.queryByRole("heading", { name: "Planning signals" })).not.toBeInTheDocument();
});

test("overview offers a bounded retry when it cannot be loaded", async () => {
  const fetchMock = stub(() => failure());

  renderWithProviders(
    <WorkspaceOverviewPanel csrfToken="csrf" includeDescendants={false} unitId="unit-1" />,
  );

  expect(await screen.findByText("The team overview could not be loaded.")).toBeVisible();
  expect(screen.queryByRole("button", { name: /Export/ })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(2));
});

test("people search forwards only queries long enough to be meaningful", async () => {
  const fetchMock = stub(() => ok({ items: [person], truncated: true }));

  renderWithProviders(<WorkspacePeoplePanel includeDescendants={false} unitId="unit-1" />);

  expect(await screen.findByRole("heading", { name: "People" })).toBeVisible();
  expect(screen.getByText("team member · 37h week")).toBeVisible();
  expect(screen.getByText("Assignment eligible")).toBeVisible();
  expect(screen.getByText("Only the first 100 matching people are shown.")).toBeVisible();

  const field = screen.getByPlaceholderText("Search by name or username");
  await userEvent.type(field, "S");
  await userEvent.click(screen.getByRole("button", { name: "Search" }));
  await userEvent.type(field, "yn");
  await userEvent.click(screen.getByRole("button", { name: "Search" }));

  await waitFor(() =>
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("query=Syn"))).toBe(true),
  );
  expect(fetchMock.mock.calls.some(([url]) => String(url).includes("query=S&"))).toBe(false);
});

test("people panel explains an empty roster and a failed load", async () => {
  const fetchMock = stub((url) =>
    String(url).includes("query=") ? failure() : ok({ items: [], truncated: false }),
  );

  renderWithProviders(<WorkspacePeoplePanel includeDescendants unitId="unit-1" />);

  expect(await screen.findByText("No authorised people match this search.")).toBeVisible();
  await userEvent.type(screen.getByPlaceholderText("Search by name or username"), "Syn");
  await userEvent.click(screen.getByRole("button", { name: "Search" }));

  expect(await screen.findByText("The authorised roster could not be loaded.")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(2));
});

test("capability coverage distinguishes gaps, cover and suppressed counts", async () => {
  stub(() =>
    ok({
      items: [
        {
          capabilityId: "regional_analysis",
          verifiedCount: 4,
          gap: false,
          display: "4",
          requiredProficiency: "practitioner",
          suppressed: false,
        },
        {
          capabilityId: "imagery",
          verifiedCount: 0,
          gap: true,
          display: "0",
          requiredProficiency: "expert",
          suppressed: false,
        },
        {
          capabilityId: "maritime",
          verifiedCount: null,
          gap: null,
          display: "<5",
          requiredProficiency: "practitioner",
          suppressed: true,
        },
      ],
    }),
  );

  renderWithProviders(<WorkspaceCapabilitiesPanel includeDescendants unitId="unit-1" />);

  const table = await screen.findByRole("table", { name: "Verified team capability coverage" });
  expect(within(table).getByRole("rowheader", { name: "regional analysis" })).toBeVisible();
  expect(within(table).getByText("Covered")).toBeVisible();
  expect(within(table).getByText("Gap")).toBeVisible();
  expect(within(table).getByText("Suppressed")).toBeVisible();
});

test("capability coverage explains an empty configuration and a failed load", async () => {
  const fetchMock = stub(() => failure());

  const { unmount } = renderWithProviders(
    <WorkspaceCapabilitiesPanel includeDescendants={false} unitId="unit-1" />,
  );

  expect(await screen.findByText("Capability coverage could not be loaded.")).toBeVisible();
  const before = fetchMock.mock.calls.length;
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(before));
  unmount();

  resetQueryClientForTests();
  stub(() => ok({ items: [] }));
  renderWithProviders(<WorkspaceCapabilitiesPanel includeDescendants={false} unitId="unit-2" />);
  expect(await screen.findByText("No capability requirements are configured.")).toBeVisible();
});
