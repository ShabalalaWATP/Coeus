import { useQuery } from "@tanstack/react-query";
import { BarChart3, LineChart, Repeat2, Star } from "lucide-react";

import { ErrorState, LoadingState } from "../../components/ui/PageState";
import {
  getAnalyticsDashboard,
  type AnalyticsAudience,
  type AnalyticsDashboard,
} from "../../lib/api-client/analytics";

type AnalyticsDashboardPageProps = {
  audience: AnalyticsAudience;
};

const titles: Record<AnalyticsAudience, string> = {
  admin: "Admin Analytics",
  rfa: "RFA Analytics",
  collection: "Collection Analytics",
};

const descriptions: Record<AnalyticsAudience, string> = {
  admin: "Global delivery, feedback and reuse analytics.",
  rfa: "Assessment route delivery, requester feedback and product reuse.",
  collection: "Collection route delivery, requester feedback and product reuse.",
};

export default function AnalyticsDashboardPage({ audience }: AnalyticsDashboardPageProps) {
  const dashboardQuery = useQuery({
    queryKey: ["analytics-dashboard", audience],
    queryFn: () => getAnalyticsDashboard(audience),
  });
  const dashboard = dashboardQuery.data;

  return (
    <div className="analytics-page">
      <section className="overview-hero" aria-labelledby="analytics-title">
        <div>
          <h1 id="analytics-title">{titles[audience]}</h1>
          <p>{descriptions[audience]}</p>
        </div>
        <div className="classification-note">MOCK DATA ONLY</div>
      </section>
      {dashboardQuery.isError ? (
        <section className="surface">
          <ErrorState onRetry={() => void dashboardQuery.refetch()} />
        </section>
      ) : dashboard ? (
        <DashboardContent dashboard={dashboard} />
      ) : (
        <LoadingState label="Loading analytics" />
      )}
    </div>
  );
}

function DashboardContent({ dashboard }: { dashboard: AnalyticsDashboard }) {
  const metricItems = [
    { label: "Tickets", value: dashboard.metrics.totalTickets, icon: BarChart3 },
    { label: "Disseminations", value: dashboard.metrics.disseminations, icon: Repeat2 },
    { label: "Feedback", value: dashboard.metrics.feedbackSubmitted, icon: Star },
    {
      label: "Average rating",
      value: dashboard.metrics.averageRating?.toFixed(1) ?? "Pending",
      icon: LineChart,
    },
  ];
  return (
    <>
      <section className="analytics-metrics" aria-label="Analytics summary">
        {metricItems.map((metric) => {
          const Icon = metric.icon;
          return (
            <article className="analytics-metric" key={metric.label}>
              <Icon aria-hidden="true" size={22} strokeWidth={1.8} />
              <strong>{metric.value}</strong>
              <span>{metric.label}</span>
            </article>
          );
        })}
      </section>
      <section className="analytics-grid">
        <ProductReuseList dashboard={dashboard} />
        <TrendList dashboard={dashboard} />
      </section>
    </>
  );
}

function ProductReuseList({ dashboard }: { dashboard: AnalyticsDashboard }) {
  return (
    <section className="surface analytics-panel" aria-labelledby="reuse-title">
      <div className="section-heading">
        <h2 id="reuse-title">Product reuse</h2>
        <p>{dashboard.productReuse.length} products with reuse signals.</p>
      </div>
      {dashboard.productReuse.length === 0 ? <p>No product reuse recorded.</p> : null}
      {dashboard.productReuse.map((product) => (
        <article className="analytics-row" key={product.productId}>
          <div>
            <strong>{product.title}</strong>
            <span>{product.reference}</span>
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
              <dt>Feedback</dt>
              <dd>{product.averageRating?.toFixed(1) ?? "Pending"}</dd>
            </div>
          </dl>
        </article>
      ))}
    </section>
  );
}

function TrendList({ dashboard }: { dashboard: AnalyticsDashboard }) {
  return (
    <section className="surface analytics-panel" aria-labelledby="trends-title">
      <div className="section-heading">
        <h2 id="trends-title">Trends Analysis Agent</h2>
        <p>{dashboard.trends.length} generated insights.</p>
      </div>
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
