import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Pencil, X } from "lucide-react";
import { useEffect, useState } from "react";

import { getMyProfile, updateMyProfile } from "../../lib/api-client/teams";
import { useActionError } from "../../lib/mutations/action-error";

const MAX_BIO = 1000;

export function ProfessionalProfileCard({ csrfToken }: { csrfToken: string }) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [specialisms, setSpecialisms] = useState("");
  const [bio, setBio] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [saved, setSaved] = useState(false);
  const { actionError, clearActionError, failActionWith } = useActionError();
  const profileQuery = useQuery({ queryKey: ["my-profile"], queryFn: getMyProfile });
  const profile = profileQuery.data;

  useEffect(() => {
    if (profile) {
      setTitle(profile.title);
      setSpecialisms(profile.specialisms.join("; "));
      setBio(profile.bio);
    }
  }, [profile]);

  const saveMutation = useMutation({
    mutationFn: () =>
      updateMyProfile(
        {
          title: title.trim(),
          specialisms: specialisms
            .split(";")
            .map((item) => item.trim())
            .filter((item) => item !== ""),
          bio: bio.trim(),
        },
        csrfToken,
      ),
    onError: failActionWith("The profile could not be saved."),
    onMutate: () => {
      clearActionError();
      setSaved(false);
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(["my-profile"], updated);
      void queryClient.invalidateQueries({ queryKey: ["teams"] });
      setIsEditing(false);
      setSaved(true);
    },
  });

  function cancelEditing() {
    if (profile) {
      setTitle(profile.title);
      setSpecialisms(profile.specialisms.join("; "));
      setBio(profile.bio);
    }
    clearActionError();
    setIsEditing(false);
  }

  return (
    <section className="profile-panel" aria-labelledby="professional-profile-title">
      <div className="profile-panel__heading">
        <h3 id="professional-profile-title">Professional profile</h3>
        {profile && !isEditing ? (
          <button
            className="profile-panel__link"
            onClick={() => {
              setSaved(false);
              setIsEditing(true);
            }}
            type="button"
          >
            <Pencil aria-hidden="true" size={15} />
            Edit profile
          </button>
        ) : null}
      </div>

      {profileQuery.isLoading ? (
        <p className="profile-muted" role="status">
          Loading your profile…
        </p>
      ) : null}
      {profileQuery.isError ? (
        <p className="profile-muted" role="alert">
          Your profile could not be loaded. Refresh and try again.
        </p>
      ) : null}

      {profile && !isEditing ? (
        <div className="profile-read-view">
          <p className="profile-read-view__title">{profile.title || "No title added"}</p>
          <ul className="profile-chips" aria-label="Specialisms">
            {profile.specialisms.length ? (
              profile.specialisms.map((specialism) => <li key={specialism}>{specialism}</li>)
            ) : (
              <li className="profile-chips__empty">No specialisms added</li>
            )}
          </ul>
          <p className="profile-bio">
            {profile.bio || "Add a short biography for your teammates."}
          </p>
          <small className="profile-muted">
            Visible to teammates and authorised administrators
            {profile.updatedAt ? ` · Updated ${formatUpdated(profile.updatedAt)}` : ""}
          </small>
        </div>
      ) : null}

      {profile && isEditing ? (
        <form
          className="profile-edit-form"
          onSubmit={(event) => {
            event.preventDefault();
            saveMutation.mutate();
          }}
        >
          <label>
            Title
            <input
              disabled={saveMutation.isPending}
              maxLength={120}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Your role or appointment"
              value={title}
            />
          </label>
          <label>
            Specialisms
            <input
              disabled={saveMutation.isPending}
              onChange={(event) => setSpecialisms(event.target.value)}
              placeholder="All-source analysis; Maritime; GEOINT"
              value={specialisms}
            />
            <small>Separate up to eight specialisms with semicolons.</small>
          </label>
          <label>
            Biography
            <textarea
              disabled={saveMutation.isPending}
              maxLength={MAX_BIO}
              onChange={(event) => setBio(event.target.value)}
              placeholder="Describe the experience and perspective you bring to the team."
              rows={6}
              value={bio}
            />
            <small>
              {bio.length}/{MAX_BIO} characters
            </small>
          </label>
          <div className="profile-edit-form__actions">
            <button className="profile-panel__link" onClick={cancelEditing} type="button">
              <X aria-hidden="true" size={15} />
              Cancel
            </button>
            <button disabled={saveMutation.isPending} type="submit">
              <Check aria-hidden="true" size={16} />
              {saveMutation.isPending ? "Saving…" : "Save changes"}
            </button>
          </div>
        </form>
      ) : null}

      {saved ? (
        <p className="profile-saved" role="status">
          Profile saved.
        </p>
      ) : null}
      {actionError ? (
        <p className="auth-error" role="alert">
          {actionError}
        </p>
      ) : null}
    </section>
  );
}

function formatUpdated(iso: string) {
  const parsed = new Date(iso);
  return Number.isNaN(parsed.getTime())
    ? iso
    : new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(parsed);
}
