import { ProfessionalProfileCard } from "./ProfessionalProfileCard";
import { ProfileAccessCard } from "./ProfileAccessCard";
import { ProfileCapabilitiesCard } from "./ProfileCapabilitiesCard";
import { ProfileIdentityCard } from "./ProfileIdentityCard";
import { useAuth } from "../../lib/auth/auth-context";

export default function ProfilePage() {
  const { session } = useAuth();
  if (!session) return null;
  const identity = session.user;

  return (
    <div className="profile-page">
      <header className="profile-page__header">
        <h1 id="profile-title">My Profile</h1>
        <p>Your identity, the access you hold and the context your teammates see.</p>
      </header>

      <div className="profile-layout">
        <ProfileIdentityCard identity={identity} />
        <div className="profile-main">
          <ProfessionalProfileCard csrfToken={session.csrfToken} />
          <ProfileAccessCard canViewAcgs={identity.permissions.includes("acg:view")} />
          <ProfileCapabilitiesCard permissions={identity.permissions} />
        </div>
      </div>
    </div>
  );
}
