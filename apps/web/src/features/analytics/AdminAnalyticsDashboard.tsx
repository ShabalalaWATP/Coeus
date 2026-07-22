import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AudioLines,
  Bot,
  Database,
  KeyRound,
  ShieldCheck,
  UserCheck,
  Users,
} from "lucide-react";

import { AdminReturnLink } from "../../components/ui/AdminReturnLink";
import { ErrorState, LoadingState } from "../../components/ui/PageState";
import {
  getAdminAnalyticsDashboard,
  type AdminAnalyticsDashboard,
} from "../../lib/api-client/analytics";

export function AdminAnalyticsDashboardPage() {
  const query = useQuery({
    queryKey: ["admin-analytics-dashboard"],
    queryFn: getAdminAnalyticsDashboard,
  });
  return (
    <div className="analytics-page admin-analytics-page">
      <section className="overview-hero analytics-hero" aria-labelledby="admin-analytics-title">
        <div>
          <AdminReturnLink />
          <h1 id="admin-analytics-title">Admin Analytics</h1>
          <p>Account, AI service, access and security health without intelligence detail.</p>
        </div>
        <div className="analytics-scope">
          <span>Current platform state</span>
          <strong>Retained 30-day activity</strong>
        </div>
      </section>
      {query.isError ? (
        <section className="surface">
          <ErrorState onRetry={() => void query.refetch()} />
        </section>
      ) : query.data ? (
        <AdminDashboard dashboard={query.data} />
      ) : (
        <LoadingState label="Loading admin analytics" />
      )}
    </div>
  );
}

function AdminDashboard({ dashboard }: { dashboard: AdminAnalyticsDashboard }) {
  const metrics = [
    {
      detail: `${dashboard.users.active} enabled · ${dashboard.users.disabled} disabled`,
      icon: Users,
      label: "User accounts",
      value: dashboard.users.total,
    },
    {
      detail: "Distinct successful sign-ins",
      icon: UserCheck,
      label: "Active users · 30d",
      value: dashboard.users.activeUsers30d,
    },
    {
      detail: `${dashboard.assistant.provider} · ${dashboard.assistant.model}`,
      icon: Bot,
      label: "Assistant chat turns · 30d",
      value: dashboard.assistant.chatTurns30d,
    },
    {
      detail: `${dashboard.audit.loginFailures30d} failed sign-ins`,
      icon: ShieldCheck,
      label: "Security events · 30d",
      value: dashboard.audit.securityEvents30d,
    },
  ];
  return (
    <>
      <section className="analytics-metrics" aria-label="Administration summary">
        {metrics.map((metric) => (
          <article className="analytics-metric" key={metric.label}>
            <metric.icon aria-hidden="true" size={20} />
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <small>{metric.detail}</small>
          </article>
        ))}
      </section>
      <section className="admin-analytics-grid" aria-label="AI service health">
        <ServiceCard
          facts={[
            ["Chat turns · 30d", dashboard.assistant.chatTurns30d],
            ["Provider requests admitted · process", dashboard.process.remoteRequestsAdmitted],
            ["Capacity denials · process", dashboard.process.remoteRequestsDenied],
          ]}
          icon={Bot}
          statuses={[
            dashboard.assistant.provider,
            dashboard.assistant.apiKeyConfigured || dashboard.assistant.provider === "mock"
              ? "Ready"
              : "Key missing",
          ]}
          subtitle={dashboard.assistant.model}
          title="Text assistant"
        />
        <ServiceCard
          facts={[
            ["Search runs · 30d", dashboard.search.searchRuns30d],
            ["Indexed passages", dashboard.search.indexedPassages],
            ["Asset warnings", dashboard.search.failedAssets],
          ]}
          icon={Database}
          statuses={[dashboard.search.provider, `Index ${dashboard.search.indexStatus}`]}
          subtitle={dashboard.search.model}
          title="Search & embeddings"
        />
        <ServiceCard
          facts={[
            ["Sessions started · 30d", dashboard.voice.sessionsStarted30d],
            ["Distinct users · 30d", dashboard.voice.users30d],
            ["Dedicated key", dashboard.voice.apiKeyConfigured ? "Saved" : "Missing"],
          ]}
          icon={AudioLines}
          statuses={[dashboard.voice.enabled ? "Enabled" : "Disabled", dashboard.voice.model]}
          subtitle="OpenAI Realtime"
          title="Voice"
        />
      </section>
      <section className="admin-analytics-lower-grid">
        <AccountEstate dashboard={dashboard} />
        <AuditCoverage dashboard={dashboard} />
      </section>
    </>
  );
}

function ServiceCard({
  facts,
  icon: Icon,
  statuses,
  subtitle,
  title,
}: {
  facts: [string, number | string][];
  icon: typeof Bot;
  statuses: string[];
  subtitle: string;
  title: string;
}) {
  return (
    <article className="surface admin-service-card">
      <div className="admin-service-card__heading">
        <Icon aria-hidden="true" size={20} />
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
      </div>
      <div className="admin-service-card__statuses">
        {statuses.map((status) => (
          <span key={status}>{status}</span>
        ))}
      </div>
      <dl>
        {facts.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </article>
  );
}

function AccountEstate({ dashboard }: { dashboard: AdminAnalyticsDashboard }) {
  return (
    <section className="surface analytics-panel" aria-labelledby="account-estate-title">
      <div className="analytics-section-heading">
        <div>
          <span className="eyebrow">Identity and access</span>
          <h2 id="account-estate-title">Account estate</h2>
        </div>
        <Users aria-hidden="true" size={20} />
      </div>
      <dl className="admin-stat-grid">
        <Stat label="Enabled accounts" value={dashboard.users.active} />
        <Stat label="Disabled accounts" value={dashboard.users.disabled} />
        <Stat label="Pending access requests" value={dashboard.users.pendingRegistrations} />
        <Stat label="Password reset required" value={dashboard.users.passwordResetRequired} />
      </dl>
      <h3 className="admin-analytics-subtitle">Role assignments</h3>
      {dashboard.users.roleCounts.length === 0 ? <p>No role assignments recorded.</p> : null}
      <div className="admin-role-list">
        {dashboard.users.roleCounts.map((role) => (
          <div key={role.role}>
            <span>{role.role}</span>
            <strong>{role.count}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function AuditCoverage({ dashboard }: { dashboard: AdminAnalyticsDashboard }) {
  return (
    <section className="surface analytics-panel" aria-labelledby="audit-coverage-title">
      <div className="analytics-section-heading">
        <div>
          <span className="eyebrow">Platform activity</span>
          <h2 id="audit-coverage-title">Security and audit</h2>
        </div>
        <Activity aria-hidden="true" size={20} />
      </div>
      <dl className="admin-stat-grid">
        <Stat label="Successful sign-ins · 30d" value={dashboard.audit.loginSuccesses30d} />
        <Stat label="Failed sign-ins · 30d" value={dashboard.audit.loginFailures30d} />
        <Stat label="Configuration changes · 30d" value={dashboard.audit.configurationChanges30d} />
        <Stat label="Retained audit events" value={dashboard.audit.retainedEvents} />
      </dl>
      <div className="admin-audit-note">
        <KeyRound aria-hidden="true" size={17} />
        <p>
          Coverage begins {formatDate(dashboard.audit.coverageStartsAt)}. Values are aggregates from
          retained events and never include usernames, prompts or intelligence records.
        </p>
      </div>
      {dashboard.audit.retentionLimitReached ? (
        <p className="workspace-alert" role="status">
          The audit retention limit has been reached, so earlier activity may not be represented.
        </p>
      ) : null}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function formatDate(value: string | null) {
  if (value === null) return "when the first event is recorded";
  return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(new Date(value));
}
