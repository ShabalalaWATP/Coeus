import { useEffect, useRef } from "react";

import { useAuth } from "../../lib/auth/auth-context";

export function LogoutUnconfirmedPage() {
  const { logout } = useAuth();
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  return (
    <main className="auth-layout" aria-labelledby="logout-unconfirmed-title">
      <section className="auth-card">
        <h1 id="logout-unconfirmed-title" ref={headingRef} tabIndex={-1}>
          Sign-out could not be confirmed
        </h1>
        <p role="alert">
          The server session may still be active. Protected data has been hidden. Retry sign-out
          before leaving this device.
        </p>
        <button onClick={() => void logout()} type="button">
          Retry sign-out
        </button>
      </section>
    </main>
  );
}

export function LogoutPendingPage() {
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  return (
    <main className="auth-layout" aria-labelledby="logout-pending-title">
      <section className="auth-card" role="status" aria-live="polite">
        <h1 id="logout-pending-title" ref={headingRef} tabIndex={-1}>
          Signing out
        </h1>
        <p>Protected data has been hidden while the server session is being revoked.</p>
      </section>
    </main>
  );
}
