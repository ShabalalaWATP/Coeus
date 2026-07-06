import { Link } from "react-router-dom";

export default function ForbiddenPage() {
  return (
    <main className="auth-message-page" aria-labelledby="forbidden-title">
      <section className="surface auth-message">
        <p className="auth-message__code">403</p>
        <h1 id="forbidden-title">Access denied</h1>
        <p>Your current role does not permit this workspace.</p>
        <Link className="text-link" to="/">
          Return to Istari
        </Link>
      </section>
    </main>
  );
}
