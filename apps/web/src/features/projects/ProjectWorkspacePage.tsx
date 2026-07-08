import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ClipboardList, FolderKanban, ShieldCheck, UsersRound } from "lucide-react";
import { Link, useLocation, useParams } from "react-router-dom";

import { EmptyState, ErrorState, LoadingState } from "../../components/ui/PageState";
import { apiClient, type ProjectWorkspace } from "../../lib/api-client/client";
import { useAuth } from "../../lib/auth/auth-context";
import { hasPermissions } from "../../lib/permissions/route-access";

type ProjectWorkspacePageProps = {
  view?: "overview" | "plan" | "members" | "products";
};

export default function ProjectWorkspacePage({ view = "overview" }: ProjectWorkspacePageProps) {
  const { projectId } = useParams();
  const { session } = useAuth();
  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () => apiClient.listProjects(),
  });
  const projects = useMemo(() => projectsQuery.data ?? [], [projectsQuery.data]);
  const project = useMemo(() => {
    if (projectId === undefined) {
      return projects[0];
    }
    return projects.find((item) => item.id === projectId);
  }, [projectId, projects]);
  const emptyTitle = projectId === undefined ? "No visible projects" : "Project not found";
  const emptyHint =
    projectId === undefined
      ? "Projects appear here once you are added as a member or requester."
      : "This project is not visible to your account or no longer exists.";
  const diagnosticProduct = project?.visibleProducts[0];
  const diagnosticProductId = diagnosticProduct?.id;
  const diagnosticUserId = session?.user.id;
  const csrfToken = session?.csrfToken;
  const canRequestDiagnostics =
    session !== null &&
    diagnosticProduct !== undefined &&
    csrfToken !== undefined &&
    hasPermissions(session.user, ["system:configure"]);
  const diagnosticsQuery = useQuery({
    enabled: canRequestDiagnostics,
    queryKey: ["product-access-diagnostics", diagnosticProductId, diagnosticUserId],
    queryFn: () =>
      apiClient.diagnoseProductAccess(
        diagnosticProductId ?? "",
        diagnosticUserId ?? "",
        csrfToken ?? "",
      ),
  });

  return (
    <div className="project-page">
      <section className="overview-hero" aria-labelledby="project-title">
        <div>
          <h1 id="project-title">Projects</h1>
          <p>MOCK DATA ONLY workspaces link requesters, teams, ACGs, plans and products.</p>
        </div>
        <div className="classification-note">MOCK DATA ONLY</div>
      </section>

      {projectsQuery.isLoading ? (
        <section className="surface">
          <LoadingState label="Loading projects" />
        </section>
      ) : null}
      {projectsQuery.isError ? (
        <section className="surface">
          <ErrorState onRetry={() => void projectsQuery.refetch()} />
        </section>
      ) : null}
      {projects.length > 0 ? (
        <nav className="surface project-picker" aria-label="Your projects">
          <span className="eyebrow">Your projects</span>
          <ul>
            {projects.map((item) => (
              <li key={item.id}>
                <Link
                  aria-current={item.id === project?.id ? "page" : undefined}
                  className={
                    item.id === project?.id
                      ? "store-action store-action--secondary project-picker__active"
                      : "store-action store-action--secondary"
                  }
                  to={`/projects/${encodeURIComponent(item.id)}`}
                >
                  <span className="mono-ref">{item.reference}</span>
                  {item.name}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      ) : null}
      {project === undefined ? (
        projectsQuery.isLoading || projectsQuery.isError ? null : (
          <section className="surface">
            <EmptyState hint={emptyHint} title={emptyTitle} />
          </section>
        )
      ) : (
        <ProjectWorkspaceContent
          diagnostics={diagnosticsQuery.data}
          project={project}
          view={view}
        />
      )}
    </div>
  );
}

type ProjectWorkspaceContentProps = {
  diagnostics?: { allowed: boolean; checks: { name: string; passed: boolean; reason: string }[] };
  project: ProjectWorkspace;
  view: "overview" | "plan" | "members" | "products";
};

function ProjectWorkspaceContent({ diagnostics, project, view }: ProjectWorkspaceContentProps) {
  const overviewPath = `/projects/${encodeURIComponent(project.id)}`;
  const location = useLocation();

  return (
    <>
      <section className="surface project-summary" aria-label="Project summary">
        <div>
          <span className="eyebrow">{project.reference}</span>
          <h2>{project.name}</h2>
          <p>{project.summary}</p>
        </div>
        <dl className="detail-list detail-list--wide">
          <div>
            <dt>ACGs</dt>
            <dd>{project.acgIds.length}</dd>
          </div>
          <div>
            <dt>Members</dt>
            <dd>{project.members.length}</dd>
          </div>
          <div>
            <dt>Visible Products</dt>
            <dd>{project.visibleProducts.length}</dd>
          </div>
        </dl>
      </section>

      <nav className="project-tabs" aria-label="Project sections">
        {view !== "overview" ? (
          <Link className="store-action store-action--secondary" to={overviewPath}>
            <ArrowLeft aria-hidden="true" size={18} />
            Overview
          </Link>
        ) : null}
        <Link className="store-action store-action--secondary" to={`${overviewPath}/plan`}>
          Plan
        </Link>
        <Link className="store-action store-action--secondary" to={`${overviewPath}/members`}>
          Members
        </Link>
        <Link className="store-action store-action--secondary" to={`${overviewPath}/products`}>
          Products
        </Link>
      </nav>

      <section className="project-grid">
        {(view === "overview" || view === "plan") && (
          <article className="surface" aria-labelledby="project-plan-title">
            <div className="section-heading access-heading">
              <ClipboardList aria-hidden="true" size={20} />
              <h2 id="project-plan-title">Plan</h2>
            </div>
            <div className="stack-list">
              {project.planItems.map((item) => (
                <div className="stack-row" key={item.id}>
                  <strong>{item.title}</strong>
                  <span>{item.ownerRole}</span>
                  <small>{item.status}</small>
                </div>
              ))}
            </div>
          </article>
        )}

        {(view === "overview" || view === "members") && (
          <article className="surface" aria-labelledby="project-members-title">
            <div className="section-heading access-heading">
              <UsersRound aria-hidden="true" size={20} />
              <h2 id="project-members-title">Members</h2>
            </div>
            <div className="stack-list">
              {project.members.map((member) => (
                <div className="stack-row" key={member.userId}>
                  <strong>{member.role}</strong>
                  <span>{member.userId}</span>
                </div>
              ))}
            </div>
          </article>
        )}

        {(view === "overview" || view === "products") && (
          <article className="surface" aria-labelledby="project-products-title">
            <div className="section-heading access-heading">
              <FolderKanban aria-hidden="true" size={20} />
              <h2 id="project-products-title">Products</h2>
            </div>
            <div className="stack-list">
              {project.visibleProducts.map((product) => (
                <Link
                  className="stack-row"
                  key={product.id}
                  state={{ from: location.pathname }}
                  to={`/store/products/${encodeURIComponent(product.id)}`}
                >
                  <strong>{product.title}</strong>
                  <span>{product.productType}</span>
                  <small>{product.status}</small>
                </Link>
              ))}
            </div>
          </article>
        )}
      </section>

      {diagnostics !== undefined ? (
        <section className="surface" aria-labelledby="diagnostics-title">
          <div className="section-heading access-heading">
            <ShieldCheck aria-hidden="true" size={20} />
            <h2 id="diagnostics-title">Access Diagnostics</h2>
          </div>
          <div className="stack-list">
            {diagnostics.checks.map((check) => (
              <div className="stack-row" key={check.name}>
                <strong>{check.name}</strong>
                <span>{check.reason}</span>
                <small>{check.passed ? "pass" : "fail"}</small>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </>
  );
}
