import { zodResolver } from "@hookform/resolvers/zod";
import { CheckCircle2, Send } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ApiError } from "../../lib/api-client/client";
import { submitRegistration } from "../../lib/api-client/registration";

const requestAccessSchema = z.object({
  displayName: z.string().min(2, "Enter your display name.").max(120),
  username: z.string().email("Enter a valid email address."),
  password: z.string().min(12, "Use at least 12 characters.").max(256),
  justification: z.string().max(1000, "Keep the justification under 1000 characters."),
});

type RequestAccessValues = z.infer<typeof requestAccessSchema>;

export function RequestAccessForm() {
  const [submitted, setSubmitted] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
  } = useForm<RequestAccessValues>({
    defaultValues: { displayName: "", justification: "", password: "", username: "" },
    resolver: zodResolver(requestAccessSchema),
  });

  async function onSubmit(values: RequestAccessValues) {
    setRequestError(null);
    try {
      await submitRegistration(values);
      setSubmitted(true);
    } catch (error) {
      if (error instanceof ApiError && error.status === 429) {
        setRequestError("Too many pending requests right now. Try again later.");
        return;
      }
      setRequestError("The request could not be submitted. Check the form and try again.");
    }
  }

  if (submitted) {
    return (
      <div className="auth-success" role="status">
        <CheckCircle2 aria-hidden="true" size={22} />
        <div>
          <strong>Request submitted.</strong>
          <p>An administrator will review your access request. You can sign in once approved.</p>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={(event) => void handleSubmit(onSubmit)(event)} noValidate>
      <div className="section-heading">
        <h2 id="request-access-title">Request access</h2>
        <p>Submissions are reviewed by an administrator before an account is created.</p>
      </div>
      <div className="form-field">
        <label htmlFor="register-display-name">Display name</label>
        <input
          autoComplete="name"
          disabled={isSubmitting}
          id="register-display-name"
          type="text"
          {...register("displayName")}
        />
        {errors.displayName ? <small>{errors.displayName.message}</small> : null}
      </div>
      <div className="form-field">
        <label htmlFor="register-username">Email</label>
        <input
          autoComplete="email"
          disabled={isSubmitting}
          id="register-username"
          type="email"
          {...register("username")}
        />
        {errors.username ? <small>{errors.username.message}</small> : null}
      </div>
      <div className="form-field">
        <label htmlFor="register-password">Password</label>
        <input
          autoComplete="new-password"
          disabled={isSubmitting}
          id="register-password"
          type="password"
          {...register("password")}
        />
        {errors.password ? <small>{errors.password.message}</small> : null}
      </div>
      <div className="form-field">
        <label htmlFor="register-justification">Justification (optional)</label>
        <textarea
          disabled={isSubmitting}
          id="register-justification"
          rows={3}
          {...register("justification")}
        />
        {errors.justification ? <small>{errors.justification.message}</small> : null}
      </div>
      {requestError ? (
        <p className="auth-error" role="alert">
          {requestError}
        </p>
      ) : null}
      <button className="primary-button" disabled={isSubmitting} type="submit">
        <Send aria-hidden="true" size={17} />
        {isSubmitting ? "Submitting request" : "Submit request"}
      </button>
    </form>
  );
}
