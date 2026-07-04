import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { IconButton } from "./IconButton";
import { renderWithProviders } from "../../test/test-utils";

test("forwards click events and accessible label", async () => {
  const user = userEvent.setup();
  const onClick = vi.fn();

  renderWithProviders(
    <IconButton ariaLabel="Run command" onClick={onClick}>
      R
    </IconButton>,
  );

  await user.click(screen.getByRole("button", { name: "Run command" }));

  expect(onClick).toHaveBeenCalledTimes(1);
});
