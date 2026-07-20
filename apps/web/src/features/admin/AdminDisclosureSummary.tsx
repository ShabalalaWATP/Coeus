import { ChevronDown, type LucideIcon } from "lucide-react";

export type AdminStatus = {
  label: string;
  tone?: "active" | "attention" | "neutral";
};

export function AdminDisclosureSummary({
  description,
  eyebrow,
  icon: Icon,
  statuses,
  title,
  titleId,
}: {
  description: string;
  eyebrow: string;
  icon: LucideIcon;
  statuses: AdminStatus[];
  title: string;
  titleId: string;
}) {
  return (
    <summary className="admin-disclosure__summary">
      <span className="admin-disclosure__icon">
        <Icon aria-hidden="true" size={20} />
      </span>
      <span className="admin-disclosure__copy">
        <span className="eyebrow">{eyebrow}</span>
        <h2 className="admin-disclosure__title" id={titleId}>
          {title}
        </h2>
        <span className="admin-disclosure__description">{description}</span>
      </span>
      <span className="admin-disclosure__statuses" aria-label={`${title} status`}>
        {statuses.map((status) => (
          <span
            className={`admin-status admin-status--${status.tone ?? "neutral"}`}
            key={status.label}
          >
            {status.label}
          </span>
        ))}
      </span>
      <ChevronDown aria-hidden="true" className="admin-disclosure__chevron" size={20} />
    </summary>
  );
}
