import {
  Archive,
  BarChart3,
  ClipboardList,
  Database,
  FileCheck2,
  LayoutDashboard,
  ListChecks,
  RadioTower,
  ScrollText,
  ShieldCheck,
} from "lucide-react";
import { Link } from "react-router-dom";

import { groupedNavigationItems, type NavigationItem } from "../../lib/permissions/route-access";

const icons = {
  requests: ClipboardList,
  store: Database,
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
  const groups = groupedNavigationItems(items);

  return (
    <aside className="nav-rail" aria-label="Primary navigation">
      <div className="brand">
        <img alt="" aria-hidden="true" className="brand__mark" src="/istari-logo-64.png" />
        <div>
          <p className="brand__name">Istari</p>
          <p className="brand__strapline">Knowledge-led intelligence tasking</p>
        </div>
      </div>
      <nav className="nav-rail__links">
        {groups.map((group) => (
          <NavGroup activePath={activePath} group={group} key={group.group} />
        ))}
      </nav>
    </aside>
  );
}

type NavGroupProps = {
  activePath: string;
  group: { group: string; label: string; items: NavigationItem[] };
};

function NavGroup({ activePath, group }: NavGroupProps) {
  return (
    <>
      <p className="nav-group" aria-hidden="true">
        {group.label}
      </p>
      {group.items.map((item) => {
        const Icon = icons[item.icon];
        const active = isActiveNavigationItem(activePath, item, group.items);
        return (
          <Link
            aria-current={active ? "page" : undefined}
            className={active ? "nav-link nav-link--active" : "nav-link"}
            key={item.path}
            to={item.path}
          >
            <Icon aria-hidden="true" size={18} strokeWidth={1.9} />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </>
  );
}

function isActiveNavigationItem(
  activePath: string,
  item: NavigationItem,
  groupItems: readonly NavigationItem[],
) {
  if (!pathMatches(activePath, item.path)) {
    return false;
  }
  return !groupItems.some(
    (candidate) =>
      candidate.path !== item.path &&
      candidate.path.length > item.path.length &&
      pathMatches(activePath, candidate.path),
  );
}

function pathMatches(activePath: string, itemPath: string) {
  return activePath === itemPath || activePath.startsWith(`${itemPath}/`);
}
