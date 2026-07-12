import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import TeamsPage from "./TeamsPage";
import { entry, now, teamsFetch, todayIso } from "./teams-page.fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const monthFormat = new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric" });

beforeEach(() => {
  resetQueryClientForTests();
  vi.stubGlobal(
    "confirm",
    vi.fn(() => true),
  );
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("adds a calendar entry for a team member", async () => {
  const fetchMock = teamsFetch();
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<TeamsPage />, "/teams");

  await screen.findByLabelText("Month grid");
  await userEvent.selectOptions(screen.getByLabelText("Member"), "analyst-1");
  await userEvent.selectOptions(screen.getByLabelText("Activity"), "course");
  await userEvent.click(screen.getByRole("button", { name: "Add entry" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/teams/team-1/calendar",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  const call = fetchMock.mock.calls.find(
    ([url, init]) => String(url).endsWith("/calendar") && init?.method === "POST",
  );
  const body: unknown = JSON.parse(call?.[1]?.body as string);
  expect(body).toMatchObject({ userId: "analyst-1", date: todayIso, status: "course" });
  expect(body).not.toHaveProperty("endDate");
});

test("adds a block entry when the dates span a range", async () => {
  const fetchMock = teamsFetch();
  vi.stubGlobal("fetch", fetchMock);
  const end = new Date(now);
  end.setDate(now.getDate() + 3);
  const endIso = [end.getFullYear(), end.getMonth() + 1, end.getDate()]
    .map((part, index) => String(part).padStart(index === 0 ? 4 : 2, "0"))
    .join("-");

  renderWithProviders(<TeamsPage />, "/teams");

  await screen.findByLabelText("Month grid");
  await userEvent.selectOptions(screen.getByLabelText("Activity"), "leave");
  fireEvent.change(screen.getByLabelText("To"), { target: { value: endIso } });
  await userEvent.click(screen.getByRole("button", { name: "Add entry" }));

  await waitFor(() => {
    const call = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/calendar") && init?.method === "POST",
    );
    expect(call).toBeDefined();
    const body: unknown = JSON.parse(call?.[1]?.body as string);
    expect(body).toMatchObject({ date: todayIso, endDate: endIso, status: "leave" });
  });
});

test("removes a calendar entry it may manage", async () => {
  const fetchMock = teamsFetch();
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<TeamsPage />, "/teams");

  await userEvent.click(
    await screen.findByRole("button", {
      name: `Remove entry for Intelligence Analyst on ${todayIso}`,
    }),
  );

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/teams/team-1/calendar/entry-1",
      expect.objectContaining({ method: "DELETE" }),
    ),
  );
});

test("highlights today in the month grid and shows the month title", async () => {
  vi.stubGlobal("fetch", teamsFetch());

  renderWithProviders(<TeamsPage />, "/teams");

  expect(await screen.findByRole("heading", { name: monthFormat.format(now) })).toBeVisible();
  await screen.findByLabelText("Month grid");
  const todayCell = screen.getByRole("button", { name: `Plan ${todayIso}` }).closest(".cal-day");
  expect(todayCell?.className).toContain("cal-day--today");
});

test("shows calendar loading feedback before rendering the month grid", async () => {
  const fallbackFetch = teamsFetch();
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) =>
      url.includes("/calendar?") ? new Promise(() => undefined) : fallbackFetch(url, init),
    ),
  );

  renderWithProviders(<TeamsPage />, "/teams");

  expect(await screen.findByText("Loading team calendar…")).toBeVisible();
  expect(screen.queryByLabelText("Month grid")).not.toBeInTheDocument();
});

test("shows an empty grid and surfaces entry failures", async () => {
  vi.stubGlobal("fetch", teamsFetch({ addEntryFails: true, calendar: { entries: [] } }));

  renderWithProviders(<TeamsPage />, "/teams");

  await screen.findByLabelText("Month grid");
  expect(screen.queryByRole("button", { name: /Remove entry/ })).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Add entry" }));
  expect(await screen.findByText("Failed.")).toBeVisible();
});

test("navigates months and picks a day into the form", async () => {
  vi.stubGlobal("fetch", teamsFetch({ calendar: { entries: [] } }));

  renderWithProviders(<TeamsPage />, "/teams");

  await screen.findByLabelText("Month grid");
  const nextMonth = new Date(now.getFullYear(), now.getMonth() + 1, 1);

  await userEvent.click(screen.getByRole("button", { name: "Next month" }));
  expect(await screen.findByRole("heading", { name: monthFormat.format(nextMonth) })).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Previous month" }));
  await userEvent.click(screen.getByRole("button", { name: "Today" }));
  expect(await screen.findByRole("heading", { name: monthFormat.format(now) })).toBeVisible();

  await userEvent.click(screen.getByRole("button", { name: `Plan ${todayIso}` }));
  expect(screen.getByLabelText("From")).toHaveValue(todayIso);
  expect(screen.getByLabelText("To")).toHaveValue(todayIso);
});

test("caps visible chips per day with an overflow count", async () => {
  const entries = ["a", "b", "c", "d"].map((suffix, index) => ({
    ...entry,
    id: `entry-${suffix}`,
    userId: index % 2 === 0 ? "analyst-1" : "preview-user",
  }));
  vi.stubGlobal("fetch", teamsFetch({ calendar: { entries } }));

  renderWithProviders(<TeamsPage />, "/teams");

  expect(await screen.findByText("+1")).toBeVisible();
});

test("block entries render on every covered day with a range confirm", async () => {
  const end = new Date(now);
  end.setDate(now.getDate() + 1);
  const endIso = [end.getFullYear(), end.getMonth() + 1, end.getDate()]
    .map((part, index) => String(part).padStart(index === 0 ? 4 : 2, "0"))
    .join("-");
  const confirmMock = vi.fn(() => false);
  vi.stubGlobal("confirm", confirmMock);
  vi.stubGlobal(
    "fetch",
    teamsFetch({ calendar: { entries: [{ ...entry, endDate: endIso, status: "course" }] } }),
  );

  renderWithProviders(<TeamsPage />, "/teams");

  const chips = await screen.findAllByRole("button", {
    name: /Remove entry for Intelligence Analyst/,
  });
  expect(chips.length).toBeGreaterThanOrEqual(2);
  await userEvent.click(chips[0]);
  expect(confirmMock).toHaveBeenCalledWith(
    `Remove Intelligence Analyst's entry (${todayIso} to ${endIso})?`,
  );
});
