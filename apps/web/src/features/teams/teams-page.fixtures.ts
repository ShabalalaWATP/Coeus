import type { OrgTeam } from "../../lib/api-client/teams";

export const team: OrgTeam = {
  id: "team-1",
  name: "RFA Assessment Team",
  kind: "rfa",
  capabilityTeamId: "RFA-MARITIME",
  members: [
    {
      userId: "preview-user",
      username: "rfa.manager@example.test",
      displayName: "RFA Manager",
      isManager: true,
      title: "Team Lead",
      specialisms: [],
      bio: "Leads the assessment team.",
    },
    {
      userId: "analyst-1",
      username: "analyst@example.test",
      displayName: "Intelligence Analyst",
      isManager: false,
      title: "Senior Imagery Analyst",
      specialisms: ["IMINT", "Maritime"],
      bio: "Maritime imagery specialist.",
    },
  ],
};

export const availability = {
  teamId: "team-1",
  date: "2026-07-10",
  members: 2,
  onLeave: 1,
  onTaskCalendar: 0,
  otherCommitments: 1,
  assignedLive: 1,
  onTask: 1,
  free: 0,
};

export const now = new Date();
export const todayIso = [now.getFullYear(), now.getMonth() + 1, now.getDate()]
  .map((part, index) => String(part).padStart(index === 0 ? 4 : 2, "0"))
  .join("-");

export const entry = {
  id: "entry-1",
  userId: "analyst-1",
  date: todayIso,
  endDate: todayIso,
  status: "leave" as const,
  note: "Annual leave.",
  createdByUserId: "analyst-1",
};

export const profile = {
  userId: "preview-user",
  title: "Team Lead",
  specialisms: ["Management"],
  bio: "MOCK DATA ONLY.",
  updatedAt: "2026-07-10T00:00:00Z",
};

export function teamsFetch(overrides: Record<string, unknown> = {}) {
  return vi.fn((url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const respond = (payload: unknown, status = 200) =>
      Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(payload) });
    if (url.endsWith("/api/v1/teams")) {
      return respond(overrides.teams ?? { teams: [team] });
    }
    if (url.includes("/availability")) {
      return respond(availability);
    }
    if (url.includes("/calendar?")) {
      return respond(overrides.calendar ?? { entries: [entry] });
    }
    if (url.includes("/calendar/") && method === "DELETE") {
      return respond(null, 204);
    }
    if (url.includes("/calendar") && method === "POST") {
      return overrides.addEntryFails
        ? respond({ error: { code: "server_error", message: "Failed." } }, 500)
        : respond({ ...entry, id: "entry-2" });
    }
    if (url.includes("/member-candidates")) {
      return respond(
        overrides.directory ?? {
          users: [
            {
              userId: "user-9",
              username: "colleague@example.test",
              displayName: "Colleague",
              isManager: false,
              title: "Liaison",
              specialisms: [],
              bio: "",
            },
          ],
        },
      );
    }
    if (url.includes("/members/") && method === "DELETE") {
      return respond(team);
    }
    if (url.includes("/members") && method === "POST") {
      return overrides.addMemberFails
        ? respond({ error: { code: "server_error", message: "Failed." } }, 500)
        : respond(team);
    }
    if (url.includes("/users/me/profile")) {
      return respond(profile);
    }
    return respond({});
  });
}
