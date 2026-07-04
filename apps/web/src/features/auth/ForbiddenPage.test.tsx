import { screen } from "@testing-library/react";

import ForbiddenPage from "./ForbiddenPage";
import { renderWithProviders } from "../../test/test-utils";

test("renders forbidden page", () => {
  renderWithProviders(<ForbiddenPage />);

  expect(screen.getByRole("heading", { name: "Access denied" })).toBeVisible();
  expect(screen.getByText("403")).toBeVisible();
});
