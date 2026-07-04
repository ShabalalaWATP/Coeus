import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { ClipboardList, FolderKanban, ShieldCheck, UsersRound } from "lucide-react";
import { useParams } from "react-router-dom";

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
  const project = useMemo(
    () => projects.find((item) => item.id === projectId) ?? projects[0],
    [projectId, projects],
  );
  const diagnosticProduct = project?.visibleProducts[0];
  const diagnosticProductId = diagnosticProduct?.id;
  const diagnosticUserId = session?.user.id;
  const diagnosticsQuery = useQuery({
    enabled:
      session !== null &&
      diagnosticProduct !== undefined &&
      hasPermissions(session.user, ["system:configure"]),
    queryKey: ["product-access-diagnostics", diagnosticProductId, diagnosticUserId],
    queryFn: () =>
      apiClient.diagnoseProductAccess(diagnosticProductId ?? "", diagnosticUserId ?? ""),
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

      {projectsQuery.isLoading ? <section className="surface">Loading projects</section> : null}
      {project === undefined ? (
        <section className="surface">No visible projects</section>
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
                <div className="stack-row" key={product.id}>
                  <strong>{product.title}</strong>
                  <span>{product.productType}</span>
                  <small>{product.status}</small>
                </div>
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
