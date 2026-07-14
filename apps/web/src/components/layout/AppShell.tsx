import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { NavigationRail } from "./NavigationRail";
import { TopCommandBar } from "./TopCommandBar";
import { useAuth } from "../../lib/auth/auth-context";
import { visibleNavigationItems } from "../../lib/permissions/route-access";
import type { UserProfile } from "../../lib/permissions/route-access";

type AppShellProps = {
  profile: UserProfile;
};

export function AppShell({ profile }: AppShellProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout } = useAuth();
  const navigationItems = visibleNavigationItems(profile);

  async function handleLogout() {
    if (await logout()) {
      void navigate("/login", { replace: true });
    }
  }

  return (
    <div className="app-shell">
      <NavigationRail activePath={location.pathname} items={navigationItems} />
      <div className="workspace">
        <TopCommandBar onLogout={handleLogout} profile={profile} />
        <main className="workspace__main" aria-label="Istari workspace">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
