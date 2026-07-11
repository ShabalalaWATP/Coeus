import { useQuery } from "@tanstack/react-query";
import { Bot } from "lucide-react";

import {
  listCapabilityCatalogue,
  type CapabilityTeam,
  type RoutingRoute,
} from "../../lib/api-client/routing";

type CapabilityCataloguePanelProps = {
  route: RoutingRoute;
  showAll?: boolean;
};

export function CapabilityCataloguePanel({
  route,
  showAll = false,
}: CapabilityCataloguePanelProps) {
  const catalogueQuery = useQuery({
    queryKey: ["capability-catalogue"],
    queryFn: listCapabilityCatalogue,
  });
  const teams = (catalogueQuery.data?.teams ?? []).filter(
    (team) => showAll || team.department === route,
  );
  const title = showAll
    ? "Capability teams"
    : route === "rfa"
      ? "RFA capability teams"
      : "Collection capability teams";

  return (
    <details className="workspace-details capability-catalogue">
      <summary>
        <Bot aria-hidden="true" size={16} />
        {title}
      </summary>
      {catalogueQuery.isError ? (
        <p role="alert">Capability catalogue could not be loaded.</p>
      ) : null}
      <div className="capability-catalogue__list">
        {teams.map((team) => (
          <CapabilityTeamRow key={team.teamId} team={team} />
        ))}
      </div>
    </details>
  );
}

function CapabilityTeamRow({ team }: { team: CapabilityTeam }) {
  const labels = team.department === "cm" ? team.sourceLabels : team.keywords;
  const badges = [
    ...(team.disciplines ?? []),
    ...(team.regions ?? []),
    ...(team.rank !== undefined ? [`rank ${team.rank}`] : []),
  ];
  return (
    <article className="capability-team">
      <strong>{team.name}</strong>
      <span>{team.teamId}</span>
      <p>{team.workPackages[0]}</p>
      <div className="capability-team__labels">
        {labels.slice(0, 3).map((label) => (
          <small key={label}>{label}</small>
        ))}
        {badges.map((badge) => (
          <small className="capability-team__badge" key={badge}>
            {badge}
          </small>
        ))}
      </div>
    </article>
  );
}
