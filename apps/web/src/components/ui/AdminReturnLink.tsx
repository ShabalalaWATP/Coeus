import { ArrowLeft } from "lucide-react";
import { Link, useInRouterContext } from "react-router-dom";

import { useAuth } from "../../lib/auth/auth-context";
import { hasPermissions } from "../../lib/permissions/route-access";

export function AdminReturnLink() {
  const { session } = useAuth();
  const inRouter = useInRouterContext();
  const isAdmin = session !== null && hasPermissions(session.user, ["system:configure"]);

  if (!isAdmin) return null;
  const content = (
    <>
      <ArrowLeft aria-hidden="true" size={15} />
      Back to Admin
    </>
  );
  return inRouter ? (
    <Link className="admin-return-link" to="/admin/overview">
      {content}
    </Link>
  ) : (
    <a className="admin-return-link" href="/admin/overview">
      {content}
    </a>
  );
}
