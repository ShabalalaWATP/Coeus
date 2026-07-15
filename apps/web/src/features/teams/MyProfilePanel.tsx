import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Pencil, ShieldCheck, X } from "lucide-react";
import { useEffect, useState } from "react";

import type { AuthUser } from "../../lib/api-client/auth";
import { getMyProfile, updateMyProfile } from "../../lib/api-client/teams";
import { useActionError } from "../../lib/mutations/action-error";

type MyProfilePanelProps = {
  csrfToken: string;
  identity: AuthUser;
};

export function MyProfilePanel({ csrfToken, identity }: MyProfilePanelProps) {
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
    <section className="profile-card" aria-label="My profile">
      <header className="profile-identity">
        <span className="profile-avatar" aria-hidden="true">
          {initials(identity.displayName)}
        </span>
        <div>
          <span className="profile-eyebrow">Your Coeus identity</span>
          <h2>{identity.displayName}</h2>
          <p>{identity.username}</p>
        </div>
        <span className="profile-verified">
          <ShieldCheck aria-hidden="true" size={16} />
          Authenticated
        </span>
      </header>
      <div className="profile-roles" aria-label="Assigned roles">
        {identity.roles.map((role) => (
          <span key={role}>{role}</span>
        ))}
      </div>

      {profileQuery.isLoading ? <p role="status">Loading your profile…</p> : null}
      {profileQuery.isError ? (
        <p role="alert">Your profile could not be loaded. Refresh and try again.</p>
      ) : null}

      {profile && !isEditing ? (
        <div className="profile-read-view">
          <div className="profile-read-view__heading">
            <div>
              <span>Professional profile</span>
              <h3>{profile.title || "No title added"}</h3>
            </div>
            <button
              className="secondary-action"
              onClick={() => {
                setSaved(false);
                setIsEditing(true);
              }}
              type="button"
            >
              <Pencil aria-hidden="true" size={16} />
              Edit profile
            </button>
          </div>
          <div className="profile-specialisms">
            {profile.specialisms.length ? (
              profile.specialisms.map((specialism) => <span key={specialism}>{specialism}</span>)
            ) : (
              <span>No specialisms added</span>
            )}
          </div>
          <p className="profile-bio">
            {profile.bio || "Add a short biography for your teammates."}
          </p>
          <small>Visible to teammates and authorised administrators.</small>
        </div>
      ) : null}

      {profile && isEditing ? (
        <form
          className="profile-edit-form border-glow"
          onSubmit={(event) => {
            event.preventDefault();
            saveMutation.mutate();
          }}
        >
          <div className="profile-edit-form__heading">
            <div>
              <span>Edit mode</span>
              <h3>Update your professional profile</h3>
            </div>
            <button aria-label="Cancel profile editing" onClick={cancelEditing} type="button">
              <X aria-hidden="true" size={18} />
            </button>
          </div>
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
              maxLength={1000}
              onChange={(event) => setBio(event.target.value)}
              placeholder="Describe the experience and perspective you bring to the team."
              rows={7}
              value={bio}
            />
            <small>{bio.length}/1000 characters</small>
          </label>
          <div className="profile-edit-form__actions">
            <button className="secondary-action" onClick={cancelEditing} type="button">
              Cancel
            </button>
            <button disabled={saveMutation.isPending} type="submit">
              <Check aria-hidden="true" size={17} />
              {saveMutation.isPending ? "Saving…" : "Save changes"}
            </button>
          </div>
        </form>
      ) : null}

      {saved ? <p role="status">Profile saved.</p> : null}
      {actionError ? (
        <p className="auth-error" role="alert">
          {actionError}
        </p>
      ) : null}
    </section>
  );
}

function initials(displayName: string) {
  return displayName
    .split(" ")
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}
