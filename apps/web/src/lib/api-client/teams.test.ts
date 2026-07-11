import {
  addCalendarEntry,
  addTeamMember,
  getMyProfile,
  listTeamCalendar,
  listTeams,
  removeCalendarEntry,
  removeTeamMember,
  teamAvailability,
  updateMyProfile,
} from "./teams";

afterEach(() => {
  vi.restoreAllMocks();
});

test("calls the team endpoints with CSRF-protected mutations", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: () => Promise.resolve({ teams: [] }),
  });
  vi.stubGlobal("fetch", fetchMock);

  await listTeams();
  await addTeamMember("team-1", "user-1", "csrf");
  await removeTeamMember("team-1", "user-1", "csrf");
  await listTeamCalendar("team-1", "2026-07-10", "2026-07-24");
  await addCalendarEntry(
    "team-1",
    { userId: "user-1", date: "2026-07-15", status: "leave", note: "Away." },
    "csrf",
  );
  await removeCalendarEntry("team-1", "entry-1", "csrf");
  await teamAvailability("team-1", "2026-07-15");

  expect(fetchMock).toHaveBeenNthCalledWith(1, "http://127.0.0.1:8001/api/v1/teams", {
    credentials: "include",
    method: "GET",
  });
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/teams/team-1/members",
    expect.objectContaining({
      body: JSON.stringify({ userId: "user-1" }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
      method: "POST",
    }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    3,
    "http://127.0.0.1:8001/api/v1/teams/team-1/members/user-1",
    expect.objectContaining({ method: "DELETE" }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    4,
    "http://127.0.0.1:8001/api/v1/teams/team-1/calendar?from=2026-07-10&to=2026-07-24",
    expect.objectContaining({ method: "GET" }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    5,
    "http://127.0.0.1:8001/api/v1/teams/team-1/calendar",
    expect.objectContaining({
      body: JSON.stringify({
        userId: "user-1",
        date: "2026-07-15",
        status: "leave",
        note: "Away.",
      }),
      method: "POST",
    }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    6,
    "http://127.0.0.1:8001/api/v1/teams/team-1/calendar/entry-1",
    expect.objectContaining({ method: "DELETE" }),
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    7,
    "http://127.0.0.1:8001/api/v1/teams/team-1/availability?date=2026-07-15",
    expect.objectContaining({ method: "GET" }),
  );
});

test("reads and updates the caller's profile", async () => {
  const profile = {
    userId: "user-1",
    title: "Analyst",
    specialisms: ["IMINT"],
    bio: "",
    updatedAt: "2026-07-10T00:00:00Z",
  };
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(profile),
  });
  vi.stubGlobal("fetch", fetchMock);

  await getMyProfile();
  await updateMyProfile({ title: "Analyst", specialisms: ["IMINT"], bio: "" }, "csrf");

  expect(fetchMock).toHaveBeenNthCalledWith(1, "http://127.0.0.1:8001/api/v1/users/me/profile", {
    credentials: "include",
    method: "GET",
  });
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/users/me/profile",
    expect.objectContaining({
      body: JSON.stringify({ title: "Analyst", specialisms: ["IMINT"], bio: "" }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
      method: "PUT",
    }),
  );
});
