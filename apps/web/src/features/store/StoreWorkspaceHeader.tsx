import type { ReactNode } from "react";

import { StoreWorkspaceNav } from "./StoreWorkspaceNav";

type StoreWorkspaceHeaderProps = {
  action?: ReactNode;
  before?: ReactNode;
  description?: string;
  showNav?: boolean;
  title: string;
  titleId?: string;
};

/**
 * One header for every Store workspace.
 *
 * The workspace tabs already name where you are, so the title stays modest and
 * the identity line is left to the sidebar rather than repeated in accent type
 * above every page.
 */
export function StoreWorkspaceHeader({
  action,
  before,
  description,
  showNav = true,
  title,
  titleId,
}: StoreWorkspaceHeaderProps) {
  return (
    <header className="store-workspace-header">
      <div className="store-workspace-header__intro">
        <div>
          {before}
          <h1 id={titleId}>{title}</h1>
          {description ? <p>{description}</p> : null}
        </div>
        {action ? <div className="store-workspace-header__action">{action}</div> : null}
      </div>
      {showNav ? <StoreWorkspaceNav /> : null}
    </header>
  );
}
