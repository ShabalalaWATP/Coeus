import { KeyRound, ShieldCheck, ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";

import type { AuthUser } from "../../lib/api-client/auth";

export function ProfileIdentityCard({ identity }: { identity: AuthUser }) {
  return (
    <section className="profile-identity-card" aria-label="Your identity">
      <span className="profile-avatar" aria-hidden="true">
        {initials(identity.displayName)}
      </span>
      <h2>{identity.displayName}</h2>
      <p className="profile-identity-card__username">{identity.username}</p>

      <ul className="profile-chips" aria-label="Assigned roles">
        {identity.roles.map((role) => (
          <li key={role}>{role}</li>
        ))}
      </ul>

      <dl className="profile-identity-card__facts">
        <div>
          <dt>Session</dt>
          <dd className="profile-status profile-status--ok">
            <ShieldCheck aria-hidden="true" size={15} />
            Authenticated
          </dd>
        </div>
        <div>
          <dt>Password</dt>
          <dd
            className={
              identity.passwordResetRequired
                ? "profile-status profile-status--warn"
                : "profile-status"
            }
          >
            {identity.passwordResetRequired ? (
              <>
                <ShieldAlert aria-hidden="true" size={15} />
                Change required
              </>
            ) : (
              "Set"
            )}
          </dd>
        </div>
      </dl>

      <Link className="profile-account-action" to="/account/password">
        <KeyRound aria-hidden="true" size={16} />
        Change password
      </Link>
    </section>
  );
}

function initials(displayName: string) {
  return displayName
    .split(" ")
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}
