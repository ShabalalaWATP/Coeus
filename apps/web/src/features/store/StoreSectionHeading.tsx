import type { ReactNode } from "react";

type StoreSectionHeadingProps = {
  actions?: ReactNode;
  count?: number;
  id?: string;
  level?: 2 | 3;
  title: string;
};

/**
 * A panel label, not a page title.
 *
 * Panels inside a workspace were introduced by a coloured category word above a
 * display-sized heading. Two lines of chrome for one label reads as noise on a
 * dense page, so the label is a single quiet line and any count sits beside it.
 */
export function StoreSectionHeading({
  actions,
  count,
  id,
  level = 2,
  title,
}: StoreSectionHeadingProps) {
  const Heading = level === 2 ? "h2" : "h3";
  return (
    <div className="store-section-heading">
      <Heading className="store-section-heading__label" id={id}>
        {title}
        {count === undefined ? null : <span className="store-section-heading__count">{count}</span>}
      </Heading>
      {actions}
    </div>
  );
}
