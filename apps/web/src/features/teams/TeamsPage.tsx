import { useQuery } from "@tanstack/react-query";
import { Users } from "lucide-react";
import { useState } from "react";

import { MyProfilePanel } from "./MyProfilePanel";
import { TeamCalendarPanel } from "./TeamCalendarPanel";
import { TeamRosterPanel } from "./TeamRosterPanel";
import { EmptyState, ErrorState, LoadingState } from "../../components/ui/PageState";
import { listTeams, teamAvailability } from "../../lib/api-client/teams";
import { useAuth } from "../../lib/auth/auth-context";

function isoToday() {
  const today = new Date();
  return [today.getFullYear(), today.getMonth() + 1, today.getDate()]
    .map((part, index) => String(part).padStart(index === 0 ? 4 : 2, "0"))
    .join("-");
}

export default function TeamsPage() {
  const { session } = useAuth();
  const csrfToken = session?.csrfToken ?? "";
  const userId = session?.user.id ?? "";
  const [selectedTeamId, setSelectedTeamId] = useState<string>();
  const teamsQuery = useQuery({ queryKey: ["teams"], queryFn: listTeams });
  const teams = teamsQuery.data?.teams ?? [];
  const team = teams.find((item) => item.id === selectedTeamId) ?? teams[0];
  const availabilityQuery = useQuery({
    enabled: team !== undefined,
    queryKey: ["team-availability", team?.id],
    queryFn: () => teamAvailability(team?.id ?? "", isoToday()),
  });

  return (
    <div className="teams-page">
      <section className="overview-hero" aria-labelledby="teams-title">
        <div>
          <h1 id="teams-title">My Team</h1>
          <p>Rosters, member profiles and the availability calendar for your teams.</p>
        </div>
        <div className="classification-note">MOCK DATA ONLY</div>
      </section>
      {teamsQuery.isLoading ? <LoadingState /> : null}
      {teamsQuery.isError ? <ErrorState onRetry={() => void teamsQuery.refetch()} /> : null}
      {teamsQuery.isSuccess && teams.length === 0 ? (
        <EmptyState
          hint="Team managers add members from their team workspace."
          title="You are not assigned to a team"
        />
      ) : null}
      {team ? (
        <>
          {teams.length > 1 ? (
            <nav className="teams-switcher" aria-label="Your teams">
              {teams.map((item) => (
                <button
                  aria-pressed={item.id === team.id}
                  key={item.id}
                  onClick={() => setSelectedTeamId(item.id)}
                  type="button"
                >
                  <Users aria-hidden="true" size={16} />
                  {item.name}
                </button>
              ))}
            </nav>
          ) : null}
          {availabilityQuery.data ? (
            <section className="surface team-availability" aria-label="Availability today">
              <h2>Availability today</h2>
              <dl>
                <div>
                  <dt>Members</dt>
                  <dd>{availabilityQuery.data.members}</dd>
                </div>
                <div>
                  <dt>On task</dt>
                  <dd>{availabilityQuery.data.onTask}</dd>
                </div>
                <div>
                  <dt>On leave</dt>
                  <dd>{availabilityQuery.data.onLeave}</dd>
                </div>
                <div>
                  <dt>Other duties</dt>
                  <dd>{availabilityQuery.data.otherCommitments}</dd>
                </div>
                <div>
                  <dt>Free</dt>
                  <dd>{availabilityQuery.data.free}</dd>
                </div>
              </dl>
            </section>
          ) : null}
          {availabilityQuery.isLoading ? <LoadingState label="Loading team availability" /> : null}
          {availabilityQuery.isError ? (
            <ErrorState onRetry={() => void availabilityQuery.refetch()} />
          ) : null}
          <div className="teams-grid">
            <TeamRosterPanel csrfToken={csrfToken} currentUserId={userId} team={team} />
            <TeamCalendarPanel csrfToken={csrfToken} currentUserId={userId} team={team} />
          </div>
        </>
      ) : null}
      <MyProfilePanel csrfToken={csrfToken} />
    </div>
  );
}
