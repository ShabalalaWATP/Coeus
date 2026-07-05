import {
  Archive,
  BarChart3,
  ClipboardList,
  Database,
  FileCheck2,
  FolderKanban,
  LayoutDashboard,
  ListChecks,
  RadioTower,
  ScrollText,
  ShieldCheck,
} from "lucide-react";
import { NavLink } from "react-router-dom";

import type { NavigationItem } from "../../lib/permissions/route-access";

const icons = {
  requests: ClipboardList,
  store: Database,
  projects: FolderKanban,
  rfa: ListChecks,
  collection: RadioTower,
  analyst: LayoutDashboard,
  qc: FileCheck2,
  analytics: BarChart3,
  admin: ShieldCheck,
  audit: ScrollText,
  archive: Archive,
} as const;

type NavigationRailProps = {
  activePath: string;
  items: NavigationItem[];
};

export function NavigationRail({ activePath, items }: NavigationRailProps) {
  return (
    <aside className="nav-rail" aria-label="Primary navigation">
      <div className="brand">
        <div className="brand__mark" aria-hidden="true">
          C
        </div>
        <div>
          <p className="brand__name">Coeus</p>
          <p className="brand__strapline">Knowledge-led intelligence tasking</p>
        </div>
      </div>
      <nav className="nav-rail__links">
        {items.map((item) => {
          const Icon = icons[item.icon];
          const active = activePath === item.path || activePath.startsWith(`${item.path}/`);
          return (
            <NavLink
              aria-current={active ? "page" : undefined}
              className={active ? "nav-link nav-link--active" : "nav-link"}
              key={item.path}
              to={item.path}
            >
              <Icon aria-hidden="true" size={18} strokeWidth={1.9} />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}
