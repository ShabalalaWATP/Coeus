import { Link } from "react-router-dom";

export default function SessionExpiredPage() {
  return (
    <main className="auth-message-page" aria-labelledby="expired-title">
      <section className="surface auth-message">
        <p className="auth-message__code">401</p>
        <h1 id="expired-title">Session expired</h1>
        <p>Sign in again to continue working in Coeus.</p>
        <Link className="text-link" to="/login">
          Sign in
        </Link>
      </section>
    </main>
  );
}
