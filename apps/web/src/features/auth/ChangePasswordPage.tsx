import { KeyRound, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError, apiClient } from "../../lib/api-client/client";
import { useAuth } from "../../lib/auth/auth-context";
import { actionErrorMessage } from "../../lib/mutations/action-error";

const MIN_PASSWORD_LENGTH = 12;

export default function ChangePasswordPage() {
  const { refreshSession, session } = useAuth();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const resetRequired = session?.passwordResetRequired === true;
  const newPasswordTooShort = newPassword.length > 0 && newPassword.length < MIN_PASSWORD_LENGTH;
  const confirmMismatch = confirmPassword.length > 0 && confirmPassword !== newPassword;
  const canSubmit =
    currentPassword.length > 0 &&
    newPassword.length >= MIN_PASSWORD_LENGTH &&
    confirmPassword === newPassword &&
    !isSaving;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }
    setFormError(null);
    setIsSaving(true);
    try {
      await apiClient.changePassword({ currentPassword, newPassword }, session?.csrfToken ?? "");
      const nextSession = await refreshSession();
      void navigate(nextSession.user.defaultRoute, { replace: true });
    } catch (error) {
      setFormError(changePasswordErrorMessage(error));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="project-page">
      <section className="overview-hero" aria-labelledby="change-password-title">
        <div>
          <h1 id="change-password-title">Change Password</h1>
          <p>Set a new password for your Istari account.</p>
        </div>
        <div className="classification-note">MOCK DATA ONLY</div>
      </section>
      <section className="surface" aria-label="Change password form">
        {resetRequired ? (
          <p className="workspace-alert" role="alert">
            <ShieldCheck aria-hidden="true" size={16} />
            You must change your password before you can continue using Istari.
          </p>
        ) : null}
        <form className="login-form" onSubmit={(event) => void submit(event)}>
          <div className="form-field">
            <label htmlFor="current-password">Current password</label>
            <input
              autoComplete="current-password"
              id="current-password"
              onChange={(event) => setCurrentPassword(event.target.value)}
              type="password"
              value={currentPassword}
            />
          </div>
          <div className="form-field">
            <label htmlFor="new-password">New password</label>
            <input
              autoComplete="new-password"
              id="new-password"
              onChange={(event) => setNewPassword(event.target.value)}
              type="password"
              value={newPassword}
            />
            {newPasswordTooShort ? (
              <small>The new password needs at least {MIN_PASSWORD_LENGTH} characters.</small>
            ) : null}
          </div>
          <div className="form-field">
            <label htmlFor="confirm-password">Confirm new password</label>
            <input
              autoComplete="new-password"
              id="confirm-password"
              onChange={(event) => setConfirmPassword(event.target.value)}
              type="password"
              value={confirmPassword}
            />
            {confirmMismatch ? <small>The passwords do not match.</small> : null}
          </div>
          {formError ? (
            <p className="auth-error" role="alert">
              {formError}
            </p>
          ) : null}
          <button className="primary-button" disabled={!canSubmit} type="submit">
            <KeyRound aria-hidden="true" size={17} />
            {isSaving ? "Saving password" : "Change password"}
          </button>
        </form>
      </section>
    </div>
  );
}

function changePasswordErrorMessage(error: unknown) {
  if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
    return "The current password is incorrect.";
  }
  if (error instanceof ApiError && error.status === 422) {
    return actionErrorMessage(error, "The new password does not meet the password policy.");
  }
  return "The password could not be changed. Try again.";
}
