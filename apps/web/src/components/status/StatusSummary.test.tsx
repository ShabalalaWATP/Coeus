import { screen } from "@testing-library/react";

import { StatusSummary } from "./StatusSummary";
import { renderWithProviders } from "../../test/test-utils";

test("renders sprint service status items", () => {
  renderWithProviders(<StatusSummary />);

  expect(screen.getByText("System Status")).toBeVisible();
  expect(screen.getByText("Data Services")).toBeVisible();
  expect(screen.getByText("Active Users")).toBeVisible();
  expect(screen.getByText("Local Time")).toBeVisible();
});
