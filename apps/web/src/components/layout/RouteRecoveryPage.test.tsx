import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";

import { RouteRecoveryPage } from "./RouteRecoveryPage";

test("explains an invalid direct route and offers safe navigation", async () => {
  const router = createMemoryRouter([
    {
      path: "/",
      loader: () =>
        Promise.reject(
          Object.assign(new Error("Not found"), {
            data: null,
            internal: false,
            status: 404,
            statusText: "Not found",
          }),
        ),
      element: <div />,
      errorElement: <RouteRecoveryPage />,
    },
  ]);
  render(<RouterProvider router={router} />);

  expect(await screen.findByRole("heading", { name: "Workspace not found" })).toBeVisible();
  expect(screen.getByRole("link", { name: "Default workspace" })).toHaveAttribute("href", "/");
  expect(screen.getByRole("button", { name: "Back" })).toBeVisible();
});

test("recovers from an unexpected render error and supports going back", async () => {
  const back = vi.spyOn(window.history, "back").mockImplementation(() => undefined);
  const router = createMemoryRouter(
    [
      {
        path: "/broken",
        loader: () => {
          throw new Error("synthetic render failure");
        },
        element: <p>Broken</p>,
        errorElement: <RouteRecoveryPage />,
      },
    ],
    { initialEntries: ["/broken"] },
  );

  render(<RouterProvider router={router} />);
  expect(await screen.findByText("This workspace could not be opened")).toBeVisible();
  expect(screen.getByText(/Return to your default workspace/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Back" }));
  expect(back).toHaveBeenCalledTimes(1);
});
