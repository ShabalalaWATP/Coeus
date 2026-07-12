import { useQuery } from "@tanstack/react-query";
import { Activity, BarChart3, ClipboardList, Database, ShieldCheck, UserCog } from "lucide-react";
import { Link } from "react-router-dom";

import { AiModelPanel } from "./AiModelPanel";
import { RegistrationApprovalsPanel } from "./RegistrationApprovalsPanel";
import { ErrorState, LoadingState } from "../../components/ui/PageState";
import { getAdminOverview } from "../../lib/api-client/admin";
import { useAuth } from "../../lib/auth/auth-context";

const adminActions = [
  {
    description: "Review access groups and membership controls.",
    icon: ShieldCheck,
    label: "Access groups",
    to: "/admin/acgs",
  },
  {
    description: "Open global delivery and reuse analytics.",
    icon: BarChart3,
    label: "Analytics",
    to: "/admin/analytics",
  },
  {
    description: "Inspect immutable authentication and workflow events.",
    icon: ClipboardList,
    label: "Audit log",
    to: "/audit",
  },
  {
    description: "Assign roles, clearance levels and account status.",
    icon: UserCog,
    label: "Users",
    to: "/admin/users",
  },
  {
    description: "Search controlled products and asset metadata.",
    icon: Database,
    label: "Store",
    to: "/store",
  },
];

export default function AdminOverviewPage() {
  const { session } = useAuth();
  const overviewQuery = useQuery({
    queryKey: ["admin-overview"],
    queryFn: getAdminOverview,
  });

  return (
    <div className="workspace-page">
      <section className="overview-hero" aria-labelledby="admin-title">
        <div>
          <h1 id="admin-title">Admin</h1>
          <p>Operational controls for access, analytics, audit and product governance.</p>
        </div>
        <div className="classification-note">MOCK DATA ONLY</div>
      </section>

      <section className="surface workspace-summary" aria-label="Admin service status">
        {overviewQuery.isLoading ? <LoadingState label="Checking admin service status" /> : null}
        {overviewQuery.isError ? <ErrorState onRetry={() => void overviewQuery.refetch()} /> : null}
        {overviewQuery.data ? (
          <div>
            <span className="eyebrow">Control plane</span>
            <h2>{overviewQuery.data?.status === "available" ? "Available" : "Checking status"}</h2>
            <p>{overviewQuery.data?.scope ?? "Admin overview service health."}</p>
          </div>
        ) : null}
        {overviewQuery.data ? <Activity aria-hidden="true" size={24} /> : null}
      </section>

      <RegistrationApprovalsPanel csrfToken={session?.csrfToken ?? ""} />

      <AiModelPanel csrfToken={session?.csrfToken ?? ""} />

      <section className="admin-action-grid" aria-label="Admin workspaces">
        {adminActions.map((item) => (
          <Link className="surface admin-action" key={item.to} to={item.to}>
            <item.icon aria-hidden="true" size={20} />
            <span>
              <strong>{item.label}</strong>
              <small>{item.description}</small>
            </span>
          </Link>
        ))}
      </section>
    </div>
  );
}
