import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  BarChart3,
  ClipboardList,
  Database,
  FolderKanban,
  ShieldCheck,
} from "lucide-react";
import { Link } from "react-router-dom";

import { apiClient } from "../../lib/api-client/client";

type AdminOverview = {
  status: string;
  scope: string;
  userId: string;
};

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
    description: "Search controlled products and asset metadata.",
    icon: Database,
    label: "Store",
    to: "/store",
  },
  {
    description: "Review project workspaces and access diagnostics.",
    icon: FolderKanban,
    label: "Projects",
    to: "/projects",
  },
];

export default function AdminOverviewPage() {
  const overviewQuery = useQuery({
    queryKey: ["admin-overview"],
    queryFn: () => apiClient.getJson<AdminOverview>("/api/v1/admin/overview"),
  });

  return (
    <div className="project-page">
      <section className="overview-hero" aria-labelledby="admin-title">
        <div>
          <h1 id="admin-title">Admin</h1>
          <p>Operational controls for access, analytics, audit and product governance.</p>
        </div>
        <div className="classification-note">MOCK DATA ONLY</div>
      </section>

      <section className="surface project-summary" aria-label="Admin service status">
        <div>
          <span className="eyebrow">Control plane</span>
          <h2>{overviewQuery.data?.status === "available" ? "Available" : "Checking status"}</h2>
          <p>{overviewQuery.data?.scope ?? "Admin overview service health."}</p>
        </div>
        <Activity aria-hidden="true" size={24} />
      </section>

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
