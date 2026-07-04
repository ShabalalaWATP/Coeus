import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { z } from "zod";

import { ApiError } from "../../lib/api-client/client";
import { useAuth } from "../../lib/auth/auth-context";

const loginSchema = z.object({
  username: z.string().email("Enter a valid username."),
  password: z.string().min(1, "Enter your password."),
});

type LoginFormValues = z.infer<typeof loginSchema>;

type LocationState = {
  from?: string;
};

export default function LoginPage() {
  const { login, session, status } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [authError, setAuthError] = useState<string | null>(null);
  const [locked, setLocked] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const from = (location.state as LocationState | null)?.from;
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
  } = useForm<LoginFormValues>({
    defaultValues: { password: "", username: "" },
    resolver: zodResolver(loginSchema),
  });

  if (status === "authenticated" && session !== null) {
    return <Navigate to={from ?? session.user.defaultRoute} replace />;
  }

  async function onSubmit(values: LoginFormValues) {
    setAuthError(null);
    setLocked(false);
    try {
      const nextSession = await login(values);
      void navigate(from ?? nextSession.user.defaultRoute, { replace: true });
    } catch (error) {
      if (error instanceof ApiError && error.code === "account_locked") {
        setLocked(true);
        setAuthError("Authentication is temporarily locked. Try again later.");
        return;
      }
      setAuthError("Authentication failed.");
    }
  }

  return (
    <main className="login-page" aria-labelledby="login-title">
      <section className="login-panel">
        <div className="login-brand">
          <div className="brand__mark" aria-hidden="true">
            C
          </div>
          <div>
            <p className="brand__name">Coeus</p>
            <p className="brand__strapline">Knowledge-led intelligence tasking</p>
          </div>
        </div>
        <div className="private-notice">
          <ShieldCheck aria-hidden="true" size={18} />
          <span>Private system. Authorised access only.</span>
        </div>
        <form
          className="login-form"
          onSubmit={(event) => void handleSubmit(onSubmit)(event)}
          noValidate
        >
          <div className="section-heading">
            <h1 id="login-title">Sign in</h1>
            <p>Use an assigned Coeus account to continue.</p>
          </div>
          <div className="form-field">
            <label htmlFor="login-username">Username</label>
            <input
              autoComplete="username"
              disabled={isSubmitting}
              id="login-username"
              type="email"
              {...register("username")}
            />
            {errors.username ? <small>{errors.username.message}</small> : null}
          </div>
          <div className="form-field">
            <label htmlFor="login-password">Password</label>
            <span className="password-field">
              <input
                autoComplete="current-password"
                disabled={isSubmitting}
                id="login-password"
                type={showPassword ? "text" : "password"}
                {...register("password")}
              />
              <button
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="password-toggle"
                disabled={isSubmitting}
                onClick={() => setShowPassword((visible) => !visible)}
                type="button"
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </span>
            {errors.password ? <small>{errors.password.message}</small> : null}
          </div>
          {authError ? (
            <p className={locked ? "auth-error auth-error--locked" : "auth-error"} role="alert">
              {authError}
            </p>
          ) : null}
          <button className="primary-button" disabled={isSubmitting || locked} type="submit">
            {isSubmitting ? "Signing in" : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
