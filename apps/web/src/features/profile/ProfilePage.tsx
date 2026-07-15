import { MyProfilePanel } from "../teams/MyProfilePanel";
import { useAuth } from "../../lib/auth/auth-context";

export default function ProfilePage() {
  const { session } = useAuth();
  if (!session) return null;

  return (
    <div className="profile-page">
      <section className="overview-hero" aria-labelledby="profile-title">
        <div>
          <h1 id="profile-title">My Profile</h1>
          <p>Keep your professional context useful to the people you work with.</p>
        </div>
        <div className="classification-note">MOCK DATA ONLY</div>
      </section>
      <MyProfilePanel csrfToken={session.csrfToken} identity={session.user} />
    </div>
  );
}
