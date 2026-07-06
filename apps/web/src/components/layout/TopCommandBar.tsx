import { Bell, LogOut, Moon, Search, Sun, UserCircle } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { IconButton } from "../ui/IconButton";
import { useTheme } from "../../lib/theme/theme-context";
import { visibleNavigationItems, type UserProfile } from "../../lib/permissions/route-access";

type TopCommandBarProps = {
  onLogout: () => void | Promise<void>;
  profile: UserProfile;
};

export function TopCommandBar({ onLogout, profile }: TopCommandBarProps) {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const [commandQuery, setCommandQuery] = useState("");
  const [openPanel, setOpenPanel] = useState<"notifications" | "profile" | null>(null);
  const commandInputRef = useRef<HTMLInputElement>(null);
  const ThemeIcon = theme === "dark" ? Sun : Moon;
  const themeLabel = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
  const commandMatches = useMemo(() => {
    const query = commandQuery.trim().toLowerCase();
    if (!query) {
      return [];
    }
    return visibleNavigationItems(profile).filter((item) =>
      item.label.toLowerCase().includes(query),
    );
  }, [commandQuery, profile]);

  useEffect(() => {
    function focusCommand(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        commandInputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", focusCommand);
    return () => window.removeEventListener("keydown", focusCommand);
  }, []);

  function openRoute(path: string) {
    setCommandQuery("");
    setOpenPanel(null);
    void navigate(path);
  }

  return (
    <header className="command-bar">
      <div className="command-search-wrap">
        <div className="command-search">
          <Search aria-hidden="true" size={18} strokeWidth={1.8} />
          <input
            aria-label="Command"
            autoComplete="off"
            id="global-command"
            onChange={(event) => setCommandQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && commandMatches[0] !== undefined) {
                event.preventDefault();
                openRoute(commandMatches[0].path);
              }
              if (event.key === "Escape") {
                setCommandQuery("");
              }
            }}
            placeholder="Go to workspace"
            ref={commandInputRef}
            type="search"
            value={commandQuery}
          />
          <kbd aria-hidden="true">Ctrl K</kbd>
        </div>
        {commandQuery.trim() ? (
          <div className="command-menu" aria-label="Command results">
            {commandMatches.map((item) => (
              <button key={item.path} onClick={() => openRoute(item.path)} type="button">
                {item.label}
              </button>
            ))}
            {commandMatches.length === 0 ? <p>No matching route.</p> : null}
          </div>
        ) : null}
      </div>
      <div className="command-bar__actions">
        <IconButton ariaLabel={themeLabel} onClick={toggleTheme}>
          <ThemeIcon aria-hidden="true" size={18} strokeWidth={1.8} />
        </IconButton>
        <IconButton
          ariaLabel="Notifications"
          onClick={() =>
            setOpenPanel((current) => (current === "notifications" ? null : "notifications"))
          }
        >
          <Bell aria-hidden="true" size={18} strokeWidth={1.8} />
        </IconButton>
        <button
          aria-label="Profile"
          className="profile-menu"
          onClick={() => setOpenPanel((current) => (current === "profile" ? null : "profile"))}
          type="button"
        >
          <UserCircle aria-hidden="true" size={20} strokeWidth={1.8} />
          <span>{profile.displayName}</span>
        </button>
        <IconButton ariaLabel="Log out" onClick={() => void onLogout()}>
          <LogOut aria-hidden="true" size={18} strokeWidth={1.8} />
        </IconButton>
        {openPanel === "notifications" ? (
          <aside className="command-popover" aria-label="Notifications panel">
            <strong>Notifications</strong>
            <p>No new notifications.</p>
          </aside>
        ) : null}
        {openPanel === "profile" ? (
          <aside className="command-popover" aria-label="Profile panel">
            <strong>{profile.displayName}</strong>
            <p>{profile.username}</p>
            <small>{profile.roles.join(", ")}</small>
          </aside>
        ) : null}
      </div>
    </header>
  );
}
