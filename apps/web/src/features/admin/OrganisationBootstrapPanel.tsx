import { useMutation, useQueryClient } from "@tanstack/react-query";
import { KeyRound, X } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";

import { bootstrapOrganisation } from "../../lib/api-client/organisation-admin";
import { useAuth } from "../../lib/auth/auth-context";

type BootstrapPanelProps = {
  onClose: () => void;
};

export function OrganisationBootstrapPanel({ onClose }: BootstrapPanelProps) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [rootName, setRootName] = useState("");
  const [rootShortName, setRootShortName] = useState("");
  const [timeZone, setTimeZone] = useState("Europe/London");
  const [description, setDescription] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [setupNonce, setSetupNonce] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      bootstrapOrganisation(
        {
          rootName: rootName.trim(),
          rootShortName: rootShortName.trim(),
          timeZone: timeZone.trim(),
          description: description.trim(),
          currentPassword,
          setupNonce,
        },
        session?.csrfToken ?? "",
      ),
    onSuccess: () => {
      setCurrentPassword("");
      setSetupNonce("");
      void queryClient.invalidateQueries({ queryKey: ["organisation-units"] });
      onClose();
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    mutation.mutate();
  };

  return (
    <section className="organisation-mutation" aria-labelledby="organisation-bootstrap-title">
      <header>
        <div>
          <span className="eyebrow">One-time setup</span>
          <h2 id="organisation-bootstrap-title">Create the organisation root</h2>
        </div>
        <button aria-label="Close organisation setup" onClick={onClose} type="button">
          <X aria-hidden="true" size={18} />
        </button>
      </header>
      <p className="organisation-bootstrap__notice">
        <KeyRound aria-hidden="true" size={18} />
        This ceremony closes permanently after the first root is created. Your password and setup
        code are verified but never stored with the organisation record.
      </p>
      <form onSubmit={submit}>
        <label>
          Root name
          <input
            autoComplete="organization"
            maxLength={120}
            onChange={(event) => setRootName(event.target.value)}
            required
            value={rootName}
          />
        </label>
        <label>
          Short name
          <input
            maxLength={32}
            onChange={(event) => setRootShortName(event.target.value)}
            required
            value={rootShortName}
          />
        </label>
        <label>
          Time zone
          <input
            maxLength={64}
            onChange={(event) => setTimeZone(event.target.value)}
            required
            value={timeZone}
          />
        </label>
        <label className="organisation-mutation__wide">
          Description
          <textarea
            maxLength={1000}
            onChange={(event) => setDescription(event.target.value)}
            value={description}
          />
        </label>
        <label>
          Current password
          <input
            autoComplete="current-password"
            onChange={(event) => setCurrentPassword(event.target.value)}
            required
            type="password"
            value={currentPassword}
          />
        </label>
        <label>
          Setup code
          <input
            autoComplete="off"
            minLength={32}
            onChange={(event) => setSetupNonce(event.target.value)}
            required
            type="password"
            value={setupNonce}
          />
        </label>
        {mutation.isError ? <p role="alert">{mutation.error.message}</p> : null}
        <button disabled={mutation.isPending} type="submit">
          {mutation.isPending ? "Creating root…" : "Create organisation root"}
        </button>
      </form>
    </section>
  );
}
