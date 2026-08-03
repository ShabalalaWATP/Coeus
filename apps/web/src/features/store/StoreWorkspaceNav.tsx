import { BookmarkCheck, FolderKanban, Rss, Search } from "lucide-react";
import { NavLink } from "react-router-dom";

const workspaces = [
  { path: "/store", label: "Discover", icon: Search, end: true },
  { path: "/store/library", label: "My Library", icon: BookmarkCheck, end: false },
  { path: "/store/projects", label: "Projects", icon: FolderKanban, end: false },
  { path: "/store/subscriptions", label: "Subscriptions", icon: Rss, end: false },
] as const;

export function StoreWorkspaceNav() {
  return (
    <nav className="store-workspace-nav" aria-label="Intelligence Store workspaces">
      {workspaces.map((workspace) => (
        <NavLink
          className={({ isActive }) =>
            isActive ? "store-workspace-nav__link is-active" : "store-workspace-nav__link"
          }
          end={workspace.end}
          key={workspace.path}
          to={workspace.path}
        >
          <workspace.icon aria-hidden="true" size={17} />
          {workspace.label}
        </NavLink>
      ))}
    </nav>
  );
}
