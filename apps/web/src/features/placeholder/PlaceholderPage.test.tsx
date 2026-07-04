import { screen } from "@testing-library/react";

import PlaceholderPage from "./PlaceholderPage";
import { renderWithProviders } from "../../test/test-utils";

test("renders a named placeholder route", () => {
  renderWithProviders(
    <PlaceholderPage title="Audit" description="Immutable audit event review shell." />,
  );

  expect(screen.getByRole("heading", { name: "Audit" })).toBeVisible();
  expect(screen.getByText("Immutable audit event review shell.")).toBeVisible();
});
