import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  GitBranch,
  Repeat2,
  Search,
  Star,
} from "lucide-react";

import { deriveAnalytics, operationalAttention } from "./analytics-metrics";
import { AdminAnalyticsDashboardPage } from "./AdminAnalyticsDashboard";
import { ErrorState, LoadingState } from "../../components/ui/PageState";
import {
  getAnalyticsDashboard,
  type AnalyticsAudience,
  type AnalyticsDashboard,
  type TeamAnalyticsAudience,
} from "../../lib/api-client/analytics";

type AnalyticsDashboardPageProps = { audience: AnalyticsAudience };

const titles: Record<TeamAnalyticsAudience, string> = {
  rfa: "RFA Analytics",
  collection: "Collection Analytics",
};

const descriptions: Record<TeamAnalyticsAudience, string> = {
  rfa: "Assessment delivery, requester feedback and product reuse.",
  collection: "Collection delivery, requester feedback and product reuse.",
};

export default function AnalyticsDashboardPage({ audience }: AnalyticsDashboardPageProps) {
  return audience === "admin" ? (
    <AdminAnalyticsDashboardPage />
  ) : (
    <TeamAnalyticsDashboardPage audience={audience} />
  );
}

function TeamAnalyticsDashboardPage({ audience }: { audience: TeamAnalyticsAudience }) {
  const dashboardQuery = useQuery({
    queryKey: ["analytics-dashboard", audience],
    queryFn: () => getAnalyticsDashboard(audience),
  });

  return (
    <div className="analytics-page">
      <section className="overview-hero analytics-hero" aria-labelledby="analytics-title">
        <div>
          <h1 id="analytics-title">{titles[audience]}</h1>
          <p>{descriptions[audience]}</p>
        </div>
        <div className="analytics-scope">
          <span>All authorised records</span>
          <strong>All time</strong>
        </div>
      </section>
      {dashboardQuery.isError ? (
        <section className="surface">
          <ErrorState onRetry={() => void dashboardQuery.refetch()} />
        </section>
      ) : dashboardQuery.data ? (
        <DashboardContent dashboard={dashboardQuery.data} />
      ) : (
        <LoadingState label="Loading analytics" />
      )}
    </div>
  );
}

function DashboardContent({ dashboard }: { dashboard: AnalyticsDashboard }) {
  const derived = deriveAnalytics(dashboard);
  const metrics = [
    {
      detail: `${dashboard.metrics.activeTickets} currently active`,
      icon: Activity,
      label: "Total workload",
      value: dashboard.metrics.totalTickets,
    },
    {
      detail: `${derived.nonActiveTickets} closed or cancelled`,
      icon: CheckCircle2,
      label: "No longer active",
      value: `${derived.nonActiveRate}%`,
    },
    {
      detail: `${derived.disseminationRate.toFixed(1)} per request`,
      icon: Repeat2,
      label: "Disseminations",
      value: dashboard.metrics.disseminations,
    },
    {
      detail: `${derived.feedbackResponseRate}% response coverage`,
      icon: Star,
      label: "Average rating",
      value: dashboard.metrics.averageRating?.toFixed(1) ?? "Pending",
    },
  ];

  return (
    <>
      <section className="analytics-metrics" aria-label="Analytics summary">
        {metrics.map((metric) => (
          <article className="analytics-metric" key={metric.label}>
            <metric.icon aria-hidden="true" size={20} />
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <small>{metric.detail}</small>
          </article>
        ))}
      </section>

      <section className="surface analytics-operations" aria-labelledby="health-title">
        <div className="analytics-section-heading">
          <div>
            <span className="eyebrow">Operational picture</span>
            <h2 id="health-title">Workflow health</h2>
          </div>
          <span>{dashboard.metrics.totalTickets} requests in scope</span>
        </div>
        <div className="analytics-health-grid">
          <ProgressGroup
            rows={[
              {
                label: "Active",
                value: dashboard.metrics.activeTickets,
                percent: derived.activeRate,
              },
              {
                label: "Closed or cancelled",
                value: derived.nonActiveTickets,
                percent: derived.nonActiveRate,
              },
            ]}
            title="Workload state"
          />
          <ProgressGroup
            rows={[
              {
                label: "RFA",
                value: dashboard.metrics.rfaRoutes,
                percent: ratio(dashboard.metrics.rfaRoutes, dashboard.metrics.totalTickets),
              },
              {
                label: "Collection",
                value: dashboard.metrics.collectionRoutes,
                percent: ratio(dashboard.metrics.collectionRoutes, dashboard.metrics.totalTickets),
              },
              {
                label: "Unrouted",
                value: derived.unroutedTickets,
                percent: ratio(derived.unroutedTickets, dashboard.metrics.totalTickets),
              },
            ]}
            title={`Route coverage · ${derived.routeCoverage}%`}
          />
          <ProgressGroup
            rows={[
              {
                label: "Submitted",
                value: dashboard.metrics.feedbackSubmitted,
                percent: derived.feedbackResponseRate,
              },
              {
                label: "Outstanding",
                value: derived.feedbackOutstanding,
                percent: ratio(derived.feedbackOutstanding, dashboard.metrics.feedbackRequested),
              },
            ]}
            title="Feedback response"
          />
        </div>
      </section>

      <section className="analytics-detail-grid">
        <OperationalSignals dashboard={dashboard} />
        <RetrievalAndReuse dashboard={dashboard} />
      </section>
      <section className="analytics-lower-grid">
        <ProductReuseList dashboard={dashboard} />
        <TrendList dashboard={dashboard} />
      </section>
    </>
  );
}

function ProgressGroup({
  rows,
  title,
}: {
  rows: { label: string; percent: number; value: number }[];
  title: string;
}) {
  return (
    <div className="analytics-progress-group">
      <h3>{title}</h3>
      {rows.map((row) => (
        <div className="analytics-progress" key={row.label}>
          <span>{row.label}</span>
          <strong>
            {row.value} · {row.percent}%
          </strong>
          <div
            aria-label={`${row.label}: ${row.percent}%`}
            aria-valuemax={100}
            aria-valuemin={0}
            aria-valuenow={row.percent}
            className="analytics-progress__track"
            role="progressbar"
          >
            <span style={{ width: `${clampPercent(row.percent)}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function OperationalSignals({ dashboard }: { dashboard: AnalyticsDashboard }) {
  const derived = deriveAnalytics(dashboard);
  const signals = operationalAttention(dashboard, derived);
  return (
    <section className="surface analytics-panel" aria-labelledby="attention-title">
      <div className="analytics-section-heading">
        <div>
          <span className="eyebrow">Decision support</span>
          <h2 id="attention-title">Needs attention</h2>
        </div>
        <AlertTriangle aria-hidden="true" size={20} />
      </div>
      <div className="analytics-signal-list">
        {signals.map((signal) => (
          <article
            className={`analytics-signal analytics-signal--${signal.tone}`}
            key={signal.label}
          >
            <strong>{signal.label}</strong>
            <p>{signal.detail}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function RetrievalAndReuse({ dashboard }: { dashboard: AnalyticsDashboard }) {
  const accepted = dashboard.productReuse.reduce(
    (total, item) => total + item.acceptedOfferCount,
    0,
  );
  return (
    <section className="surface analytics-panel" aria-labelledby="evidence-title">
      <div className="analytics-section-heading">
        <div>
          <span className="eyebrow">Evidence flow</span>
          <h2 id="evidence-title">Search and reuse</h2>
        </div>
        <Search aria-hidden="true" size={20} />
      </div>
      <dl className="analytics-evidence">
        <div>
          <dt>Average search candidates</dt>
          <dd>{dashboard.metrics.averageSearchCandidates?.toFixed(1) ?? "No baseline"}</dd>
        </div>
        <div>
          <dt>Products with reuse signals</dt>
          <dd>{dashboard.productReuse.length}</dd>
        </div>
        <div>
          <dt>Accepted product offers</dt>
          <dd>{accepted}</dd>
        </div>
      </dl>
    </section>
  );
}

function ProductReuseList({ dashboard }: { dashboard: AnalyticsDashboard }) {
  return (
    <section className="surface analytics-panel" aria-labelledby="reuse-title">
      <div className="analytics-section-heading">
        <div>
          <span className="eyebrow">Reuse leaderboard</span>
          <h2 id="reuse-title">Products creating value</h2>
        </div>
        <Repeat2 aria-hidden="true" size={20} />
      </div>
      {dashboard.productReuse.length === 0 ? <p>No product reuse recorded.</p> : null}
      <div className="analytics-reuse-table" aria-label="Product reuse">
        {dashboard.productReuse.map((product) => (
          <article className="analytics-row" key={product.productId}>
            <div>
              <strong>{product.title}</strong>
              <span>
                {product.reference} · {product.ownerTeam}
              </span>
            </div>
            <dl>
              <div>
                <dt>Disseminated</dt>
                <dd>{product.disseminationCount}</dd>
              </div>
              <div>
                <dt>Accepted</dt>
                <dd>{product.acceptedOfferCount}</dd>
              </div>
              <div>
                <dt>Rating</dt>
                <dd>{product.averageRating?.toFixed(1) ?? "Pending"}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>
    </section>
  );
}

function TrendList({ dashboard }: { dashboard: AnalyticsDashboard }) {
  return (
    <section className="surface analytics-panel" aria-labelledby="trends-title">
      <div className="analytics-section-heading">
        <div>
          <span className="eyebrow">Generated interpretation</span>
          <h2 id="trends-title">Trend signals</h2>
        </div>
        <GitBranch aria-hidden="true" size={20} />
      </div>
      {dashboard.trends.length === 0 ? <p>No trend signals are available yet.</p> : null}
      {dashboard.trends.map((trend) => (
        <article className={`trend trend--${trend.signal}`} key={trend.title}>
          <strong>{trend.title}</strong>
          <p>{trend.summary}</p>
          <span>{Math.round(trend.confidence * 100)} percent confidence</span>
        </article>
      ))}
    </section>
  );
}

function ratio(value: number, total: number) {
  return total === 0 ? 0 : clampPercent(Math.round((value / total) * 100));
}

function clampPercent(value: number) {
  return Math.min(100, Math.max(0, value));
}
