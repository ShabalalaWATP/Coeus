import { capabilityAreas, describedPermissionCount } from "./permission-capabilities";

export function ProfileCapabilitiesCard({ permissions }: { permissions: readonly string[] }) {
  const areas = capabilityAreas(permissions);
  if (areas.length === 0) return null;
  return (
    <section className="profile-panel" aria-labelledby="profile-capabilities-title">
      <div className="profile-panel__heading">
        <h3 id="profile-capabilities-title">
          What you can do
          <span className="profile-panel__count">{describedPermissionCount(permissions)}</span>
        </h3>
      </div>
      <div className="profile-capability-grid">
        {areas.map((area) => (
          <div className="profile-capability" key={area.name}>
            <h4>{area.name}</h4>
            <ul>
              {area.capabilities.map((capability) => (
                <li key={capability}>{capability}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <p className="profile-muted">
        Your roles grant these. Every action is still authorised by the server when you take it.
      </p>
    </section>
  );
}
