import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { CollaboratorsPanel } from "./CollaboratorsPanel";
import { requestTicket as ticket } from "./requests-test-data";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("searches the directory once three characters are typed", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () =>
      Promise.resolve({
        users: [
          { id: "colleague-1", username: "colleague@example.test", displayName: "Colleague One" },
        ],
      }),
  });
  vi.stubGlobal("fetch", fetchMock);
  const onAdd = vi.fn();

  renderWithProviders(
    <CollaboratorsPanel
      isOwner
      isPending={false}
      onAdd={onAdd}
      onRemove={vi.fn()}
      ticket={ticket}
    />,
  );

  await userEvent.type(screen.getByLabelText("Search users"), "co");
  expect(screen.getByText("Type at least 3 characters to search.")).toBeVisible();
  expect(fetchMock).not.toHaveBeenCalled();

  await userEvent.type(screen.getByLabelText("Search users"), "l");
  expect(await screen.findByRole("option", { name: "Colleague One" })).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/users/directory?q=col",
    expect.objectContaining({ method: "GET" }),
  );

  await userEvent.selectOptions(screen.getByLabelText("Tag a user"), "colleague@example.test");
  await userEvent.click(screen.getByRole("button", { name: "Tag user" }));
  expect(onAdd).toHaveBeenCalledWith("colleague@example.test", "viewer");
});

test("reports directory search failures", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: () => Promise.resolve({ error: { code: "validation_error", message: "Too short." } }),
    }),
  );

  renderWithProviders(
    <CollaboratorsPanel
      isOwner
      isPending={false}
      onAdd={vi.fn()}
      onRemove={vi.fn()}
      ticket={ticket}
    />,
  );

  await userEvent.type(screen.getByLabelText("Search users"), "abc");
  expect(
    await screen.findByText("The user directory could not be searched. Try again.", undefined, {
      timeout: 5000,
    }),
  ).toBeVisible();
});

test("reports empty directory search results", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ users: [] }) }),
  );

  renderWithProviders(
    <CollaboratorsPanel
      isOwner
      isPending={false}
      onAdd={vi.fn()}
      onRemove={vi.fn()}
      ticket={ticket}
    />,
  );

  await userEvent.type(screen.getByLabelText("Search users"), "abcd");
  expect(await screen.findByText("No matching users found.")).toBeVisible();
});
