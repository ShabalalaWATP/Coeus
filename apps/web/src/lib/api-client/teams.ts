import { apiRequestJson, apiRequestNoContent, pathSegment } from "./client";

type TeamMember = {
  userId: string;
  username: string;
  displayName: string;
  isManager: boolean;
  title: string;
  specialisms: string[];
  bio: string;
};

export async function listTeamMemberCandidates(
  teamId: string,
  query: string,
): Promise<{ users: TeamMember[] }> {
  return apiRequestJson<{ users: TeamMember[] }>(
    `/api/v1/teams/${pathSegment(teamId)}/member-candidates?query=${encodeURIComponent(query)}`,
    { method: "GET" },
  );
}

export type OrgTeam = {
  id: string;
  name: string;
  kind: "rfa" | "cm" | "jioc" | "qc";
  capabilityTeamId: string | null;
  members: TeamMember[];
};

export type CalendarEntry = {
  id: string;
  userId: string;
  date: string;
  status: "available" | "on_task" | "leave";
  note: string;
  createdByUserId: string | null;
};

export type TeamAvailability = {
  teamId: string;
  date: string;
  members: number;
  onLeave: number;
  onTaskCalendar: number;
  assignedLive: number;
  onTask: number;
  free: number;
};

export type UserProfile = {
  userId: string;
  title: string;
  specialisms: string[];
  bio: string;
  updatedAt: string;
};

export async function listTeams(): Promise<{ teams: OrgTeam[] }> {
  return apiRequestJson<{ teams: OrgTeam[] }>("/api/v1/teams", { method: "GET" });
}

export async function addTeamMember(
  teamId: string,
  userId: string,
  csrfToken: string,
): Promise<OrgTeam> {
  return apiRequestJson<OrgTeam>(`/api/v1/teams/${pathSegment(teamId)}/members`, {
    body: JSON.stringify({ userId }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function removeTeamMember(
  teamId: string,
  userId: string,
  csrfToken: string,
): Promise<OrgTeam> {
  return apiRequestJson<OrgTeam>(
    `/api/v1/teams/${pathSegment(teamId)}/members/${pathSegment(userId)}`,
    { headers: { "X-CSRF-Token": csrfToken }, method: "DELETE" },
  );
}

export async function listTeamCalendar(
  teamId: string,
  from: string,
  to: string,
): Promise<{ entries: CalendarEntry[] }> {
  const query = `?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`;
  return apiRequestJson<{ entries: CalendarEntry[] }>(
    `/api/v1/teams/${pathSegment(teamId)}/calendar${query}`,
    { method: "GET" },
  );
}

export async function addCalendarEntry(
  teamId: string,
  payload: { userId: string; date: string; status: CalendarEntry["status"]; note?: string },
  csrfToken: string,
): Promise<CalendarEntry> {
  return apiRequestJson<CalendarEntry>(`/api/v1/teams/${pathSegment(teamId)}/calendar`, {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function removeCalendarEntry(
  teamId: string,
  entryId: string,
  csrfToken: string,
): Promise<void> {
  await apiRequestNoContent(
    `/api/v1/teams/${pathSegment(teamId)}/calendar/${pathSegment(entryId)}`,
    { headers: { "X-CSRF-Token": csrfToken }, method: "DELETE" },
  );
}

export async function teamAvailability(teamId: string, date: string): Promise<TeamAvailability> {
  return apiRequestJson<TeamAvailability>(
    `/api/v1/teams/${pathSegment(teamId)}/availability?date=${encodeURIComponent(date)}`,
    { method: "GET" },
  );
}

export async function getMyProfile(): Promise<UserProfile> {
  return apiRequestJson<UserProfile>("/api/v1/users/me/profile", { method: "GET" });
}

export async function updateMyProfile(
  payload: { title: string; specialisms: string[]; bio: string },
  csrfToken: string,
): Promise<UserProfile> {
  return apiRequestJson<UserProfile>("/api/v1/users/me/profile", {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "PUT",
  });
}
