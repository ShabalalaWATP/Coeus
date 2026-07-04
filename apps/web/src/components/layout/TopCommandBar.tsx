import { Bell, Moon, Search, Sun, UserCircle } from "lucide-react";

import { IconButton } from "../ui/IconButton";
import { useTheme } from "../../lib/theme/theme-context";
import type { UserProfile } from "../../lib/permissions/route-access";

type TopCommandBarProps = {
  profile: UserProfile;
};

export function TopCommandBar({ profile }: TopCommandBarProps) {
  const { theme, toggleTheme } = useTheme();
  const ThemeIcon = theme === "dark" ? Sun : Moon;
  const themeLabel = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";

  return (
    <header className="command-bar">
      <label className="command-search" htmlFor="global-command">
        <Search aria-hidden="true" size={18} strokeWidth={1.8} />
        <span className="sr-only">Command</span>
        <input id="global-command" type="search" placeholder="Command" />
      </label>
      <div className="command-bar__actions">
        <IconButton ariaLabel={themeLabel} onClick={toggleTheme}>
          <ThemeIcon aria-hidden="true" size={18} strokeWidth={1.8} />
        </IconButton>
        <IconButton ariaLabel="Notifications">
          <Bell aria-hidden="true" size={18} strokeWidth={1.8} />
        </IconButton>
        <button className="profile-menu" type="button" aria-label="Profile">
          <UserCircle aria-hidden="true" size={20} strokeWidth={1.8} />
          <span>{profile.displayName}</span>
        </button>
      </div>
    </header>
  );
}
