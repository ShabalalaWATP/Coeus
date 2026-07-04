import { screen } from "@testing-library/react";

import SessionExpiredPage from "./SessionExpiredPage";
import { renderWithProviders } from "../../test/test-utils";

test("renders session expired page", () => {
  renderWithProviders(<SessionExpiredPage />);

  expect(screen.getByRole("heading", { name: "Session expired" })).toBeVisible();
  expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
});
