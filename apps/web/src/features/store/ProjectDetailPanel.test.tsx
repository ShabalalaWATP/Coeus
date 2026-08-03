import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ProjectDetailPanel } from "./ProjectDetailPanel";
import { projectDetail } from "./store-organisation.fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => resetQueryClientForTests());

test("supports the owner and member project workflow", async () => {
  const detail = {
    ...projectDetail,
    members: [
      ...projectDetail.members,
      {
        displayName: "Research Partner",
        id: "member-2",
        owner: false,
        username: "partner@example.test",
      },
    ],
  };
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(detail) });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<ProjectDetailPanel project={detail} />, "/store/projects/project-1");

  await userEvent.type(screen.getByLabelText("Username"), "new@example.test");
  await userEvent.click(screen.getByRole("button", { name: "Add member" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

  await userEvent.click(screen.getByRole("button", { name: "Remove Research Partner" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

  await userEvent.selectOptions(screen.getByLabelText("Type"), "question");
  await userEvent.type(screen.getByLabelText("Text"), "What changed this week?");
  await userEvent.click(screen.getByRole("button", { name: "Add question" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));

  await userEvent.click(
    screen.getByRole("button", { name: "Remove Regional Stability Brief from project" }),
  );
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));

  await userEvent.click(screen.getByRole("button", { name: "Archive project" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5));
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/store/projects/project-1/status",
    expect.objectContaining({ body: JSON.stringify({ archived: true }), method: "PUT" }),
  );
});

test("renders an archived member view without owner controls", () => {
  renderWithProviders(
    <ProjectDetailPanel
      project={{
        ...projectDetail,
        activity: [
          {
            action: "future_action",
            actorDisplayName: "Research Partner",
            id: "activity-2",
            occurredAt: "2026-08-02T10:00:00Z",
          },
        ],
        archived: true,
        dateFrom: null,
        dateTo: null,
        entries: [
          {
            author: projectDetail.members[0],
            body: "Retained research note",
            createdAt: "2026-08-02T10:00:00Z",
            id: "entry-1",
            kind: "note",
          },
        ],
        owner: false,
        products: [],
        region: null,
      }}
    />,
  );

  expect(screen.getByText("Archived")).toBeVisible();
  expect(screen.getByText("Date not recorded")).toBeVisible();
  expect(screen.getByText("Retained research note")).toBeVisible();
  expect(screen.getByText(/updated the project/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Restore project" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Add note" })).not.toBeInTheDocument();
});

test("lets the owner restore an archived project without exposing active controls", async () => {
  const archived = { ...projectDetail, archived: true };
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ ...projectDetail, archived: false }),
  });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<ProjectDetailPanel project={archived} />);

  expect(screen.queryByRole("button", { name: /Remove .* from project/ })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Restore project" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/store/projects/project-1/status",
      expect.objectContaining({ body: JSON.stringify({ archived: false }), method: "PUT" }),
    ),
  );
});

test("surfaces a bounded project mutation failure", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  renderWithProviders(<ProjectDetailPanel project={projectDetail} />);

  await userEvent.click(screen.getByRole("button", { name: "Archive project" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "The project change could not be saved.",
  );
});
