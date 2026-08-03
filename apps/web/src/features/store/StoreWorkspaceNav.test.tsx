import { screen } from "@testing-library/react";

import { StoreWorkspaceNav } from "./StoreWorkspaceNav";
import { renderWithProviders } from "../../test/test-utils";

test("separates discovery, private library, projects and subscriptions", () => {
  renderWithProviders(<StoreWorkspaceNav />, "/store/projects/project-1");

  expect(screen.getByRole("link", { name: "Discover" })).toHaveAttribute("href", "/store");
  expect(screen.getByRole("link", { name: "My Library" })).toHaveAttribute(
    "href",
    "/store/library",
  );
  expect(screen.getByRole("link", { name: "Projects" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("link", { name: "Subscriptions" })).toHaveAttribute(
    "href",
    "/store/subscriptions",
  );
});
