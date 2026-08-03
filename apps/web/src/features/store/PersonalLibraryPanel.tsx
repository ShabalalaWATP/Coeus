import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookmarkCheck, Folder, FolderPlus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  createPersonalStoreFolder,
  deletePersonalStoreFolder,
  getPersonalStoreLibrary,
} from "../../lib/api-client/store";
import { useAuth } from "../../lib/auth/auth-context";

export function PersonalLibraryPanel({
  alwaysOpen = false,
  defaultOpen = false,
}: {
  /** True when the library is the whole page, so it needs no toggle. */
  alwaysOpen?: boolean;
  defaultOpen?: boolean;
}) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [folderName, setFolderName] = useState("");
  const [selected, setSelected] = useState("all");
  const [toggledOpen, setToggledOpen] = useState(defaultOpen);
  const open = alwaysOpen || toggledOpen;
  const library = useQuery({
    enabled: open,
    queryKey: ["store-library"],
    queryFn: getPersonalStoreLibrary,
  });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["store-library"] });
  const createFolder = useMutation({
    mutationFn: () => createPersonalStoreFolder(folderName.trim(), session?.csrfToken ?? ""),
    onSuccess: (folder) => {
      setFolderName("");
      setSelected(folder.id);
      refresh();
    },
  });
  const deleteFolder = useMutation({
    mutationFn: (folderId: string) => deletePersonalStoreFolder(folderId, session?.csrfToken ?? ""),
    onSuccess: () => {
      setSelected("all");
      refresh();
    },
  });
  const savedProducts = useMemo(() => {
    const products = library.data?.savedProducts ?? [];
    if (selected === "all") return products;
    if (selected === "unfiled") return products.filter((item) => item.folderId === null);
    return products.filter((item) => item.folderId === selected);
  }, [library.data?.savedProducts, selected]);
  const folders = library.data?.folders ?? [];
  const savedCount = library.data?.savedProducts?.length ?? null;

  return (
    <section className="surface personal-library" aria-labelledby="personal-library-title">
      {/* Embedded in Discover the library is a one-line strip to return to, not
          the thing a search-first workspace should open with. On its own page it
          is the content, so the strip and its toggle are dropped entirely. */}
      {alwaysOpen ? (
        <h2 className="sr-only" id="personal-library-title">
          Saved intelligence
        </h2>
      ) : (
        <div className="personal-library__bar">
          <h2 id="personal-library-title">
            <BookmarkCheck aria-hidden="true" size={17} />
            Saved intelligence
          </h2>
          <p>Reports you have kept, in folders only you can see.</p>
          <button
            aria-expanded={open}
            className="personal-library__toggle"
            onClick={() => setToggledOpen((current) => !current)}
            type="button"
          >
            {open
              ? "Close my library"
              : `Open my library${savedCount === null ? "" : ` (${savedCount})`}`}
          </button>
        </div>
      )}

      {open ? (
        <>
          <form
            className="personal-library__create"
            onSubmit={(event) => {
              event.preventDefault();
              if (folderName.trim()) createFolder.mutate();
            }}
          >
            <label htmlFor="personal-folder-name">New personal folder</label>
            <div>
              <input
                id="personal-folder-name"
                maxLength={80}
                onChange={(event) => setFolderName(event.target.value)}
                placeholder="For example, Eastern Europe"
                value={folderName}
              />
              <button disabled={!folderName.trim() || createFolder.isPending} type="submit">
                <FolderPlus aria-hidden="true" size={17} />
                Create folder
              </button>
            </div>
          </form>

          <div className="personal-library__body">
            <nav className="personal-library__folders" aria-label="Personal folders">
              <FolderButton
                active={selected === "all"}
                label="All saved"
                onClick={() => setSelected("all")}
              />
              <FolderButton
                active={selected === "unfiled"}
                label="Unfiled"
                onClick={() => setSelected("unfiled")}
              />
              {folders.map((folder) => (
                <div className="personal-library__folder-row" key={folder.id}>
                  <FolderButton
                    active={selected === folder.id}
                    label={folder.name}
                    onClick={() => setSelected(folder.id)}
                  />
                  <button
                    aria-label={`Delete ${folder.name} folder`}
                    className="personal-library__delete"
                    disabled={deleteFolder.isPending}
                    onClick={() => deleteFolder.mutate(folder.id)}
                    title="Delete folder and keep its reports unfiled"
                    type="button"
                  >
                    <Trash2 aria-hidden="true" size={15} />
                  </button>
                </div>
              ))}
            </nav>

            <div className="personal-library__reports" aria-live="polite">
              {library.isLoading ? <p>Loading your saved intelligence…</p> : null}
              {library.isError ? (
                <p className="auth-error">Your saved intelligence is unavailable.</p>
              ) : null}
              {savedProducts.map((item) => (
                <Link
                  className="personal-library__report"
                  key={item.product.id}
                  state={{ from: "/store", origin: "library" }}
                  to={`/store/products/${encodeURIComponent(item.product.id)}`}
                >
                  <span>
                    <span className="mono-ref">{item.product.reference}</span>
                    <strong>{item.product.title}</strong>
                  </span>
                  <small>{item.product.areaOrRegion}</small>
                </Link>
              ))}
              {!library.isLoading && !library.isError && savedProducts.length === 0 ? (
                <p>
                  No reports in this folder yet. Open a report and choose{" "}
                  <strong>Save report</strong>.
                </p>
              ) : null}
              {(library.data?.unavailableCount ?? 0) > 0 ? (
                <small>
                  {library.data?.unavailableCount} saved report
                  {library.data?.unavailableCount === 1 ? " is" : "s are"} no longer available to
                  you.
                </small>
              ) : null}
            </div>
          </div>
          {createFolder.isError || deleteFolder.isError ? (
            <p className="auth-error" role="alert">
              Your folder change could not be saved. Try again.
            </p>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

function FolderButton({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      aria-current={active ? "page" : undefined}
      className="personal-library__folder"
      onClick={onClick}
      type="button"
    >
      <Folder aria-hidden="true" size={16} />
      {label}
    </button>
  );
}
