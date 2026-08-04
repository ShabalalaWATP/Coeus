import { useQuery } from "@tanstack/react-query";
import { Gauge } from "lucide-react";

import { getTeamCapacityForecast } from "../../lib/api-client/team-capacity-forecast";

function nextSevenDays() {
  const start = new Date();
  start.setUTCHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setUTCDate(end.getUTCDate() + 7);
  return { start: start.toISOString(), end: end.toISOString() };
}

function hours(minutes: number) {
  return new Intl.NumberFormat("en-GB", { maximumFractionDigits: 1 }).format(minutes / 60);
}

export function TeamCapacitySummary({ unitId, grantId }: { unitId: string; grantId: string }) {
  const window = nextSevenDays();
  const query = useQuery({
    queryKey: ["team-capacity", unitId, grantId, window.start],
    queryFn: () => getTeamCapacityForecast(unitId, grantId, window.start, window.end),
    retry: false,
  });
  if (query.isLoading) return <p className="team-capacity__message">Calculating team capacity…</p>;
  if (query.isError) {
    return (
      <p className="team-capacity__message" role="status">
        Team capacity is temporarily unavailable. Assignment checks still apply when work is
        planned.
      </p>
    );
  }
  const result = query.data!;
  return (
    <section className="team-capacity" aria-labelledby="team-capacity-title">
      <header>
        <Gauge aria-hidden="true" size={17} />
        <div>
          <h5 id="team-capacity-title">Next 7 days</h5>
          <p>Advisory capacity for active analysts in this team</p>
        </div>
      </header>
      {result.status === "unknown" ? (
        <p>Capacity cannot be calculated from the current workforce evidence.</p>
      ) : (
        <dl>
          <div>
            <dt>Assignable</dt>
            <dd>{hours(result.assignableMinutes)} hours</dd>
          </div>
          <div>
            <dt>Working time</dt>
            <dd>{hours(result.physicalMinutes)} hours</dd>
          </div>
          <div>
            <dt>Already reserved</dt>
            <dd>{hours(result.reservationMinutes)} hours</dd>
          </div>
          <div>
            <dt>Analysts included</dt>
            <dd>{result.peopleIncluded}</dd>
          </div>
        </dl>
      )}
      {result.status === "partial" ? (
        <p className="team-capacity__notice">
          Some workforce evidence is unavailable, so this forecast is incomplete.
        </p>
      ) : null}
    </section>
  );
}
