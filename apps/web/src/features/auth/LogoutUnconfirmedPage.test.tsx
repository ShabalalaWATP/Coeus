import { render, screen } from "@testing-library/react";

import { LogoutPendingPage, LogoutUnconfirmedPage } from "./LogoutUnconfirmedPage";
import { AuthProvider } from "../../lib/auth/auth-context";
import { previewSession } from "../../test/test-utils";

test("focuses and announces an unconfirmed sign-out without nesting controls in the alert", () => {
  render(
    <AuthProvider authApi={{} as never} initialSession={previewSession}>
      <LogoutUnconfirmedPage />
    </AuthProvider>,
  );

  const heading = screen.getByRole("heading", { name: "Sign-out could not be confirmed" });
  expect(heading).toHaveFocus();
  expect(screen.getByRole("alert")).toHaveTextContent("server session may still be active");
  expect(screen.getByRole("button", { name: "Retry sign-out" })).not.toHaveAttribute(
    "role",
    "alert",
  );
});

test("focuses and announces the pending sign-out state", () => {
  render(<LogoutPendingPage />);

  expect(screen.getByRole("heading", { name: "Signing out" })).toHaveFocus();
  expect(screen.getByRole("status")).toHaveTextContent("Protected data has been hidden");
});
