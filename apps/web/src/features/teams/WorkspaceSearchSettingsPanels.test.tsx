import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { WorkspaceSearchPanel } from "./WorkspaceSearchPanel";
import { WorkspaceSettingsPanel } from "./WorkspaceSettingsPanel";
import { WorkspaceStoreLinksPanel } from "./WorkspaceStoreLinksPanel";
import { failure, jsonBody, ok, policy, stub } from "./workspace-panels.fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(resetQueryClientForTests);
afterEach(() => vi.restoreAllMocks());
test("workspace search only runs on a submitted term and reports both outcomes", async () => {
  const fetchMock = stub((url) =>
    String(url).includes("query=Missing")
      ? ok({ items: [], truncated: false, nextCursor: null })
      : ok({
          items: [
            {
              resultType: "store_project",
              objectId: "project-1",
              unitId: "unit-1",
              label: "Regional project",
              context: "Store",
            },
          ],
          truncated: false,
          nextCursor: null,
        }),
  );
  const onSelect = vi.fn();

  renderWithProviders(
    <WorkspaceSearchPanel includeDescendants onSelect={onSelect} storeOnly unitId="unit-1" />,
  );

  expect(screen.getByRole("heading", { name: "Find an authorised Store item" })).toBeVisible();
  const submit = screen.getByRole("button", { name: "Search" });
  expect(submit).toBeDisabled();
  expect(fetchMock).not.toHaveBeenCalled();

  const field = screen.getByPlaceholderText("Report or project title");
  await userEvent.type(field, "Regional");
  await userEvent.click(submit);

  await userEvent.click(await screen.findByRole("button", { name: "Select" }));
  expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ objectId: "project-1" }));
  expect(String(fetchMock.mock.calls[0]?.[0])).toContain("store_only=true");

  await userEvent.clear(field);
  await userEvent.type(field, "Missing");
  await userEvent.click(submit);
  expect(await screen.findByText("No authorised matches found.")).toBeVisible();
});

test("workspace search surfaces a failure without claiming an empty result", async () => {
  stub(() => failure());

  renderWithProviders(<WorkspaceSearchPanel includeDescendants={false} unitId="unit-1" />);

  await userEvent.type(screen.getByPlaceholderText(/Team, work package/), "Regional");
  await userEvent.click(screen.getByRole("button", { name: "Search" }));

  expect(await screen.findByText("Search could not be completed.")).toBeVisible();
  expect(screen.queryByText("No authorised matches found.")).not.toBeInTheDocument();
});

test("settings edit every planning guardrail and save against the held grant", async () => {
  const fetchMock = stub((url, init) =>
    init?.method === "PUT" ? ok({ ...policy, wipLimit: 12, version: 4 }) : ok(policy),
  );

  renderWithProviders(
    <WorkspaceSettingsPanel
      configurationGrant={{ id: "grant-1", version: 2 }}
      csrfToken="csrf"
      unitId="unit-1"
    />,
  );

  expect(await screen.findByRole("heading", { name: "Settings" })).toBeVisible();
  await userEvent.clear(screen.getByLabelText(/Work in progress limit/));
  await userEvent.type(screen.getByLabelText(/Work in progress limit/), "12");
  await userEvent.clear(screen.getByLabelText(/Service target/));
  await userEvent.type(screen.getByLabelText(/Service target/), "48");
  await userEvent.selectOptions(screen.getByLabelText(/Planning cadence/), "monthly");
  await userEvent.selectOptions(screen.getByLabelText(/Planning day/), "2");
  await userEvent.clear(screen.getByLabelText(/Window duration/));
  await userEvent.type(screen.getByLabelText(/Window duration/), "45");
  await userEvent.click(screen.getByRole("button", { name: /Save planning settings/ }));

  expect(await screen.findByRole("status")).toHaveTextContent("Team planning settings saved.");
  const saved = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
  expect(jsonBody(saved?.[1])).toMatchObject({
    authorisingGrantId: "grant-1",
    expectedGrantVersion: 2,
    expectedVersion: 3,
    planningCadence: "monthly",
    planningWeekday: 2,
    planningDurationMinutes: 45,
    serviceTargetHours: 48,
    wipLimit: 12,
  });
});

test("settings report a rejected save without discarding the draft", async () => {
  stub((url, init) => (init?.method === "PUT" ? failure(409) : ok(policy)));

  renderWithProviders(
    <WorkspaceSettingsPanel
      configurationGrant={{ id: "grant-1", version: 2 }}
      csrfToken="csrf"
      unitId="unit-1"
    />,
  );

  await userEvent.click(await screen.findByRole("button", { name: /Save planning settings/ }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Settings changed or your authority expired. Refresh and try again.",
  );
  expect(screen.getByLabelText(/Work in progress limit/)).toHaveValue(8);
});

test("settings offer a retry when the policy cannot be loaded", async () => {
  const fetchMock = stub(() => failure());

  renderWithProviders(
    <WorkspaceSettingsPanel
      configurationGrant={{ id: "grant-1", version: 2 }}
      csrfToken="csrf"
      unitId="unit-1"
    />,
  );

  expect(await screen.findByText("Team planning settings could not be loaded.")).toBeVisible();
  expect(screen.queryByRole("button", { name: /Save planning settings/ })).not.toBeInTheDocument();
  const before = fetchMock.mock.calls.length;
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(before));
});

test("store links add and remove authorised items for a work package", async () => {
  const link = {
    linkId: "link-1",
    unitId: "unit-1",
    sourceType: "work_package",
    sourceId: "package-1",
    targetType: "product",
    targetId: "product-1",
    label: "Regional assessment",
    version: 1,
  };
  let listed = [link];
  const fetchMock = stub((url, init) => {
    const value = String(url);
    if (value.includes("/search")) {
      return ok({
        items: [
          {
            resultType: "store_project",
            objectId: "project-1",
            unitId: "unit-1",
            label: "Regional project",
            context: "Store",
          },
        ],
        truncated: false,
        nextCursor: null,
      });
    }
    if (init?.method === "DELETE") {
      listed = [];
      return ok({});
    }
    if (init?.method === "PUT") return ok(link);
    return ok({ items: listed, nextCursor: null });
  });
  const onClose = vi.fn();

  renderWithProviders(
    <WorkspaceStoreLinksPanel
      includeDescendants={false}
      onClose={onClose}
      packageId="package-1"
      packageTitle="Draft assessment"
      unitId="unit-1"
    />,
  );

  expect(await screen.findByRole("link", { name: /Regional assessment/ })).toHaveAttribute(
    "href",
    "/store/product-1",
  );

  await userEvent.type(screen.getByPlaceholderText("Report or project title"), "Regional");
  await userEvent.click(screen.getByRole("button", { name: "Search" }));
  await userEvent.click(await screen.findByRole("button", { name: "Select" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Store item linked to this package.");
  const linked = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
  expect(jsonBody(linked?.[1])).toMatchObject({
    sourceType: "work_package",
    sourceId: "package-1",
    targetType: "project",
    targetId: "project-1",
  });

  await userEvent.click(screen.getByRole("button", { name: "Remove Regional assessment" }));
  expect(await screen.findByText("No currently authorised Store items are linked.")).toBeVisible();

  await userEvent.click(screen.getByRole("button", { name: "Close Intelligence Store links" }));
  expect(onClose).toHaveBeenCalled();
});

test("a linked project points at the Store project route", async () => {
  stub((url) =>
    String(url).includes("/store-links")
      ? ok({
          items: [
            {
              linkId: "link-2",
              unitId: "unit-1",
              sourceType: "work_package",
              sourceId: "package-1",
              targetType: "project",
              targetId: "project-1",
              label: "Regional project",
              version: 1,
            },
          ],
          nextCursor: null,
        })
      : ok({ items: [], truncated: false, nextCursor: null }),
  );

  renderWithProviders(
    <WorkspaceStoreLinksPanel
      includeDescendants={false}
      onClose={vi.fn()}
      packageId="package-1"
      packageTitle="Draft assessment"
      unitId="unit-1"
    />,
  );

  expect(await screen.findByRole("link", { name: /Regional project/ })).toHaveAttribute(
    "href",
    "/store/projects/project-1",
  );
});

test("store links report a failed load without implying there are none", async () => {
  stub((url) => (String(url).includes("/store-links") ? failure() : ok({ items: [] })));

  renderWithProviders(
    <WorkspaceStoreLinksPanel
      includeDescendants
      onClose={vi.fn()}
      packageId="package-1"
      packageTitle="Draft assessment"
      unitId="unit-1"
    />,
  );

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Authorised links could not be loaded.",
  );
  expect(
    screen.queryByText("No currently authorised Store items are linked."),
  ).not.toBeInTheDocument();
});
