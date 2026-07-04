import { Outlet, useLocation } from "react-router-dom";

import { NavigationRail } from "./NavigationRail";
import { TopCommandBar } from "./TopCommandBar";
import { visibleNavigationItems } from "../../lib/permissions/route-access";
import type { UserProfile } from "../../lib/permissions/route-access";

type AppShellProps = {
  profile: UserProfile;
};

export function AppShell({ profile }: AppShellProps) {
  const location = useLocation();
  const navigationItems = visibleNavigationItems(profile);

  return (
    <div className="app-shell">
      <NavigationRail activePath={location.pathname} items={navigationItems} />
      <div className="workspace">
        <TopCommandBar profile={profile} />
        <main className="workspace__main" aria-label="Coeus workspace">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
