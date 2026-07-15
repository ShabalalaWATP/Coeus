import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { RequestDashboard } from "./RequestDashboard";
import { requestTicket as ticket } from "./requests-test-data";

const dashboardDefaults = {
  canCreate: true,
  currentUserId: "preview-user",
  isConfirming: false,
  onConfirmDelivery: vi.fn(),
};

test("opens tickets from the dashboard and shows tagged counts", async () => {
  const onOpen = vi.fn();
  render(
    <RequestDashboard
      {...dashboardDefaults}
      onOpen={onOpen}
      tickets={[
        ticket,
        {
          ...ticket,
          id: "ticket-2",
          reference: "TCK-0002",
          collaborators: [
            {
              userId: "colleague-1",
              username: "colleague@example.test",
              displayName: "Customer Colleague",
              access: "viewer",
              addedByUserId: "preview-user",
              createdAt: "2026-07-06T00:00:00Z",
            },
          ],
        },
      ]}
    />,
  );

  await userEvent.click(screen.getByRole("button", { name: /TCK-0001/ }));

  expect(onOpen).toHaveBeenCalledWith("ticket-1");
  expect(screen.getByText("1 tagged")).toBeVisible();
});

test("links released products from the dashboard", () => {
  render(
    <MemoryRouter>
      <RequestDashboard
        {...dashboardDefaults}
        onOpen={vi.fn()}
        tickets={[
          {
            ...ticket,
            state: "DISSEMINATION_READY",
            releasedProductIds: ["product-9"],
          },
        ]}
      />
    </MemoryRouter>,
  );

  expect(screen.getByRole("link", { name: /View released product/ })).toHaveAttribute(
    "href",
    "/store/products/product-9",
  );
});

test("lets the owner confirm receipt of a disseminated request", async () => {
  const onConfirmDelivery = vi.fn();
  render(
    <MemoryRouter>
      <RequestDashboard
        {...dashboardDefaults}
        onConfirmDelivery={onConfirmDelivery}
        onOpen={vi.fn()}
        tickets={[{ ...ticket, state: "DISSEMINATION_READY" }]}
      />
    </MemoryRouter>,
  );

  await userEvent.click(screen.getByRole("button", { name: "Confirm receipt and close" }));

  expect(onConfirmDelivery).toHaveBeenCalledWith("ticket-1");
});

test("hides the confirm receipt action from non-owners and closed requests", () => {
  const { rerender } = render(
    <MemoryRouter>
      <RequestDashboard
        {...dashboardDefaults}
        currentUserId="someone-else"
        onOpen={vi.fn()}
        tickets={[{ ...ticket, state: "DISSEMINATION_READY" }]}
      />
    </MemoryRouter>,
  );

  expect(
    screen.queryByRole("button", { name: "Confirm receipt and close" }),
  ).not.toBeInTheDocument();

  rerender(
    <MemoryRouter>
      <RequestDashboard
        {...dashboardDefaults}
        onOpen={vi.fn()}
        tickets={[{ ...ticket, state: "CLOSED_DELIVERED" }]}
      />
    </MemoryRouter>,
  );
  expect(
    screen.queryByRole("button", { name: "Confirm receipt and close" }),
  ).not.toBeInTheDocument();
  expect(screen.getByText("Closed delivered")).toBeVisible();
});

test("renders fallback titles and an empty dashboard state", () => {
  const { rerender } = render(
    <RequestDashboard
      {...dashboardDefaults}
      onOpen={vi.fn()}
      tickets={[{ ...ticket, intake: { ...ticket.intake, title: null } }]}
    />,
  );

  expect(screen.getByText("Draft request")).toBeVisible();

  rerender(
    <RequestDashboard {...dashboardDefaults} canCreate={false} onOpen={vi.fn()} tickets={[]} />,
  );
  expect(screen.getByText("No requests yet")).toBeVisible();
  expect(
    screen.getByText("Requests shared with you appear here once you are tagged."),
  ).toBeVisible();

  rerender(<RequestDashboard {...dashboardDefaults} onOpen={vi.fn()} tickets={[]} />);
  expect(
    screen.getByText("Open a new request and the assistant will capture the details in chat."),
  ).toBeVisible();
});
