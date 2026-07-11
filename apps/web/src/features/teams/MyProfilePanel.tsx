import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { IdCard } from "lucide-react";
import { useEffect, useState } from "react";

import { getMyProfile, updateMyProfile } from "../../lib/api-client/teams";
import { useActionError } from "../../lib/mutations/action-error";

export function MyProfilePanel({ csrfToken }: { csrfToken: string }) {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [specialisms, setSpecialisms] = useState("");
  const [bio, setBio] = useState("");
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
    onMutate: clearActionError,
    onSuccess: (updated) => {
      queryClient.setQueryData(["my-profile"], updated);
      void queryClient.invalidateQueries({ queryKey: ["teams"] });
    },
  });

  return (
    <section className="surface my-profile" aria-label="My profile">
      <div className="section-heading">
        <IdCard aria-hidden="true" size={20} />
        <h2>My profile</h2>
      </div>
      <p>Teammates see your title and specialisms beside your name on the roster.</p>
      {profileQuery.isLoading ? <p role="status">Loading your profile…</p> : null}
      {profileQuery.isError ? (
        <p role="alert">
          Your profile could not be loaded. You can still enter replacement details below.
        </p>
      ) : null}
      <form
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
            value={title}
          />
        </label>
        <label>
          Specialisms (semicolon separated)
          <input
            disabled={saveMutation.isPending}
            onChange={(event) => setSpecialisms(event.target.value)}
            placeholder="IMINT; Maritime"
            value={specialisms}
          />
        </label>
        <label>
          Bio
          <textarea
            disabled={saveMutation.isPending}
            maxLength={1000}
            onChange={(event) => setBio(event.target.value)}
            value={bio}
          />
        </label>
        <button disabled={saveMutation.isPending} type="submit">
          Save profile
        </button>
      </form>
      {saveMutation.isSuccess ? <p role="status">Profile saved.</p> : null}
      {actionError ? (
        <p className="auth-error" role="alert">
          {actionError}
        </p>
      ) : null}
    </section>
  );
}
