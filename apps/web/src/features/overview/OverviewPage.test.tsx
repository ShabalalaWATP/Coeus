import { screen } from "@testing-library/react";

import OverviewPage from "./OverviewPage";
import { renderWithProviders } from "../../test/test-utils";

test("renders the request workspace overview", () => {
  renderWithProviders(<OverviewPage />);

  expect(screen.getByRole("heading", { name: "Requests" })).toBeVisible();
  expect(screen.getByText("MOCK DATA ONLY")).toBeVisible();
  expect(screen.getByText("No request selected")).toBeVisible();
  expect(screen.getByText("No recent activity")).toBeVisible();
});
