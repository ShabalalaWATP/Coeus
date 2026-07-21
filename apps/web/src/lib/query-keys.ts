export const queryKeys = {
  teams: {
    availability: (teamId: string, date: string) =>
      ["teams", teamId, "availability", date] as const,
    availabilityPrefix: (teamId: string) => ["teams", teamId, "availability"] as const,
  },
  routing: {
    assignmentAvailability: (route: string, teamId: string, date: string) =>
      ["routing", "assignment", route, teamId, "availability", date] as const,
  },
} as const;
