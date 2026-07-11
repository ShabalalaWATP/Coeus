import { KeyRound, LogOut, Moon, Search, Sun, UserCircle } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { NotificationsPopover } from "./NotificationsPopover";
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
  const [activeCommandIndex, setActiveCommandIndex] = useState(0);
  const [openPanel, setOpenPanel] = useState<"notifications" | "profile" | null>(null);
  const commandInputRef = useRef<HTMLInputElement>(null);
  const actionsRef = useRef<HTMLDivElement>(null);
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

  // Close open popovers on Escape and on clicks outside the actions cluster,
  // matching the RequestJourney modal behaviour.
  useEffect(() => {
    if (openPanel === null) {
      return;
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpenPanel(null);
      }
    }
    function onPointerDown(event: MouseEvent) {
      if (actionsRef.current !== null && !actionsRef.current.contains(event.target as Node)) {
        setOpenPanel(null);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("mousedown", onPointerDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("mousedown", onPointerDown);
    };
  }, [openPanel]);

  function openRoute(path: string) {
    setCommandQuery("");
    setOpenPanel(null);
    void navigate(path);
  }

  const activeCommand = commandMatches[activeCommandIndex] ?? commandMatches[0];

  return (
    <header className="command-bar">
      <div className="command-search-wrap">
        <div className="command-search">
          <Search aria-hidden="true" size={18} strokeWidth={1.8} />
          <input
            aria-activedescendant={
              activeCommand ? `command-result-${activeCommandIndex}` : undefined
            }
            aria-autocomplete="list"
            aria-controls="command-results"
            aria-expanded={commandQuery.trim().length > 0}
            aria-label="Command"
            autoComplete="off"
            id="global-command"
            onChange={(event) => {
              setCommandQuery(event.target.value);
              setActiveCommandIndex(0);
            }}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown" && commandMatches.length) {
                event.preventDefault();
                setActiveCommandIndex((current) => (current + 1) % commandMatches.length);
              }
              if (event.key === "ArrowUp" && commandMatches.length) {
                event.preventDefault();
                setActiveCommandIndex(
                  (current) => (current - 1 + commandMatches.length) % commandMatches.length,
                );
              }
              if (event.key === "Enter" && activeCommand !== undefined) {
                event.preventDefault();
                openRoute(activeCommand.path);
              }
              if (event.key === "Escape") {
                setCommandQuery("");
              }
            }}
            placeholder="Go to workspace"
            ref={commandInputRef}
            type="search"
            role="combobox"
            value={commandQuery}
          />
          <kbd aria-hidden="true">Ctrl K</kbd>
        </div>
        {commandQuery.trim() ? (
          <div
            className="command-menu"
            aria-label="Command results"
            id="command-results"
            role="listbox"
          >
            {commandMatches.map((item, index) => (
              <button
                aria-selected={index === activeCommandIndex}
                id={`command-result-${index}`}
                key={item.path}
                onClick={() => openRoute(item.path)}
                role="option"
                type="button"
              >
                {item.label}
              </button>
            ))}
            {commandMatches.length === 0 ? <p>No matching route.</p> : null}
          </div>
        ) : null}
      </div>
      <div className="command-bar__actions" ref={actionsRef}>
        <IconButton ariaLabel={themeLabel} onClick={toggleTheme}>
          <ThemeIcon aria-hidden="true" size={18} strokeWidth={1.8} />
        </IconButton>
        <NotificationsPopover
          onToggle={() =>
            setOpenPanel((current) => (current === "notifications" ? null : "notifications"))
          }
          open={openPanel === "notifications"}
        />
        <button
          aria-controls="profile-panel"
          aria-expanded={openPanel === "profile"}
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
        {openPanel === "profile" ? (
          <aside className="command-popover" aria-label="Profile panel" id="profile-panel">
            <strong>{profile.displayName}</strong>
            <p>{profile.username}</p>
            <small>{profile.roles.join(", ")}</small>
            <Link
              className="store-action store-action--secondary"
              onClick={() => setOpenPanel(null)}
              to="/account/password"
            >
              <KeyRound aria-hidden="true" size={15} />
              Change password
            </Link>
          </aside>
        ) : null}
      </div>
    </header>
  );
}
