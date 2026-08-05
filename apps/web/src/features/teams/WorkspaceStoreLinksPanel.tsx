import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Link2, Trash2, X } from "lucide-react";

import {
  deleteStoreLink,
  getStoreLinks,
  saveStoreLink,
  type StoreLink,
} from "../../lib/api-client/workspace-productivity";
import type { WorkspaceSearchResult } from "../../lib/api-client/workspace-operations";
import { useAuth } from "../../lib/auth/auth-context";
import { WorkspaceSearchPanel } from "./WorkspaceSearchPanel";

export function WorkspaceStoreLinksPanel({
  includeDescendants,
  onClose,
  packageId,
  packageTitle,
  unitId,
}: {
  includeDescendants: boolean;
  onClose: () => void;
  packageId: string;
  packageTitle: string;
  unitId: string;
}) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const queryKey = ["workspace-store-links", unitId, packageId];
  const links = useQuery({
    queryKey,
    queryFn: () => getStoreLinks(unitId, "work_package", packageId),
    retry: false,
  });
  const save = useMutation({
    mutationFn: (result: WorkspaceSearchResult) =>
      saveStoreLink(
        unitId,
        {
          sourceType: "work_package",
          sourceId: packageId,
          targetType: result.resultType === "store_project" ? "project" : "product",
          targetId: result.objectId,
        },
        session!.csrfToken,
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey }),
  });
  const remove = useMutation({
    mutationFn: (link: StoreLink) => deleteStoreLink(unitId, link, session!.csrfToken),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey }),
  });
  return (
    <section className="workspace-store-links" aria-labelledby="workspace-store-links-title">
      <header>
        <div>
          <Link2 aria-hidden="true" size={17} />
          <h5 id="workspace-store-links-title">Intelligence Store links</h5>
          <p>{packageTitle}</p>
        </div>
        <button aria-label="Close Intelligence Store links" onClick={onClose} type="button">
          <X aria-hidden="true" size={16} />
        </button>
      </header>
      <p>
        Links preserve independent Store and team access. Items disappear here if your current
        product or project access is removed.
      </p>
      {links.isError ? <p role="alert">Authorised links could not be loaded.</p> : null}
      {links.data?.items.length ? (
        <ul aria-label="Linked Intelligence Store items">
          {links.data.items.map((link) => (
            <li key={link.linkId}>
              <a
                href={
                  link.targetType === "product"
                    ? "/store/" + link.targetId
                    : "/store/projects/" + link.targetId
                }
              >
                <ExternalLink aria-hidden="true" size={14} />
                {link.label}
              </a>
              <button
                aria-label={"Remove " + link.label}
                disabled={remove.isPending}
                onClick={() => remove.mutate(link)}
                type="button"
              >
                <Trash2 aria-hidden="true" size={14} /> Remove
              </button>
            </li>
          ))}
        </ul>
      ) : links.isSuccess ? (
        <p>No currently authorised Store items are linked.</p>
      ) : null}
      <WorkspaceSearchPanel
        includeDescendants={includeDescendants}
        onSelect={(result) => save.mutate(result)}
        storeOnly
        unitId={unitId}
      />
      {save.isError ? <p role="alert">The Store item could not be linked.</p> : null}
      {save.isSuccess ? <p role="status">Store item linked to this package.</p> : null}
    </section>
  );
}
