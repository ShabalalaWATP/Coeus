import { AlertTriangle, ArrowLeft, Home } from "lucide-react";
import { isRouteErrorResponse, Link, useRouteError } from "react-router-dom";

export function RouteRecoveryPage() {
  const error = useRouteError();
  const notFound = isRouteErrorResponse(error) && error.status === 404;
  return (
    <main className="route-recovery">
      <div>
        <img alt="" aria-hidden="true" src="/istari-logo-256.png" />
        <AlertTriangle aria-hidden="true" size={24} />
        <p className="eyebrow">Istari workspace</p>
        <h1>{notFound ? "Workspace not found" : "This workspace could not be opened"}</h1>
        <p>
          {notFound
            ? "The address may be outdated or unavailable to your account."
            : "Return to your default workspace. If the problem continues, contact an administrator."}
        </p>
        <div className="route-recovery__actions">
          <button onClick={() => window.history.back()} type="button">
            <ArrowLeft aria-hidden="true" size={17} /> Back
          </button>
          <Link to="/">
            <Home aria-hidden="true" size={17} /> Default workspace
          </Link>
        </div>
      </div>
    </main>
  );
}
