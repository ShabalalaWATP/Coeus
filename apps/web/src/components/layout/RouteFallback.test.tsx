import { screen } from "@testing-library/react";

import { RouteFallback } from "./RouteFallback";
import { renderWithProviders } from "../../test/test-utils";

test("announces route loading state", () => {
  renderWithProviders(<RouteFallback />);

  expect(screen.getByLabelText("Loading route")).toHaveTextContent("Loading workspace");
});
