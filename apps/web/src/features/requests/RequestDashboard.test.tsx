import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { RequestDashboard } from "./RequestDashboard";
import { requestTicket as ticket } from "./requests-test-data";

const dashboardDefaults = {
  canCreate: true,
  currentUserId: "preview-user",
  isDecidingOutcome: false,
  onProductDecision: vi.fn(),
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

test("links a joined request to its canonical work item", () => {
  render(
    <MemoryRouter>
      <RequestDashboard
        {...dashboardDefaults}
        onOpen={vi.fn()}
        tickets={[
          {
            ...ticket,
            customerStatus: {
              ...ticket.customerStatus!,
              canonicalTicketId: "canonical-ticket-2",
            },
          },
        ]}
      />
    </MemoryRouter>,
  );

  expect(screen.getByRole("link", { name: /Track joined request/ })).toHaveAttribute(
    "href",
    "/app/requests/canonical-ticket-2",
  );
});

test("lets the owner accept a released product", async () => {
  const onProductDecision = vi.fn();
  render(
    <MemoryRouter>
      <RequestDashboard
        {...dashboardDefaults}
        onProductDecision={onProductDecision}
        onOpen={vi.fn()}
        tickets={[{ ...ticket, state: "DISSEMINATION_READY" }]}
      />
    </MemoryRouter>,
  );

  await userEvent.click(screen.getByRole("button", { name: "Yes, close request" }));

  expect(onProductDecision).toHaveBeenCalledWith(
    "ticket-1",
    true,
    "The released product meets the requirement.",
    [],
  );
});

test("requires a reason before requesting re-analysis", async () => {
  const onProductDecision = vi.fn();
  render(
    <MemoryRouter>
      <RequestDashboard
        {...dashboardDefaults}
        onProductDecision={onProductDecision}
        onOpen={vi.fn()}
        tickets={[{ ...ticket, state: "DISSEMINATION_READY" }]}
      />
    </MemoryRouter>,
  );

  await userEvent.click(screen.getByRole("button", { name: "No, request re-analysis" }));
  const send = screen.getByRole("button", { name: "Send to manager for review" });
  expect(send).toBeDisabled();
  await userEvent.type(screen.getByLabelText(/Why does it not meet/), "Coverage is incomplete.");
  await userEvent.type(screen.getByLabelText(/Unmet criteria/), "Eastern sector, July");
  await userEvent.click(send);

  expect(onProductDecision).toHaveBeenCalledWith("ticket-1", false, "Coverage is incomplete.", [
    "Eastern sector",
    "July",
  ]);
});

test("hides the confirm receipt action from non-owners and closed requests", async () => {
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

  expect(screen.queryByRole("button", { name: "Yes, close request" })).not.toBeInTheDocument();

  rerender(
    <MemoryRouter>
      <RequestDashboard
        {...dashboardDefaults}
        onOpen={vi.fn()}
        tickets={[{ ...ticket, state: "CLOSED_DELIVERED" }]}
      />
    </MemoryRouter>,
  );
  expect(screen.queryByRole("button", { name: "Yes, close request" })).not.toBeInTheDocument();
  await userEvent.click(screen.getByText("Closed requests"));
  expect(screen.getByText("Closed delivered")).toBeVisible();
});

test("keeps closed requests in a disclosure that is collapsed by default", async () => {
  render(
    <MemoryRouter>
      <RequestDashboard
        {...dashboardDefaults}
        onOpen={vi.fn()}
        tickets={[
          ticket,
          { ...ticket, id: "closed-ticket", reference: "TCK-0099", state: "CLOSED_DELIVERED" },
        ]}
      />
    </MemoryRouter>,
  );

  expect(screen.getByRole("heading", { name: "Your requests" })).toBeVisible();
  expect(screen.getByRole("button", { name: /TCK-0001/ })).toBeVisible();
  expect(screen.getByRole("button", { name: /TCK-0099/ })).not.toBeVisible();

  await userEvent.click(screen.getByText("Closed requests"));

  expect(screen.getByRole("button", { name: /TCK-0099/ })).toBeVisible();
});

function grouped() {
  return render(
    <MemoryRouter>
      <RequestDashboard
        {...dashboardDefaults}
        onOpen={vi.fn()}
        tickets={[
          { ...ticket, id: "draft", reference: "TCK-0001", state: "DRAFT_INTAKE" },
          {
            ...ticket,
            id: "acting",
            reference: "TCK-0002",
            state: "RFI_MATCH_OFFERED",
            updatedAt: "2026-07-01T00:00:00Z",
          },
          {
            ...ticket,
            id: "working",
            reference: "TCK-0003",
            state: "ANALYST_IN_PROGRESS",
            updatedAt: "2026-07-09T00:00:00Z",
          },
          { ...ticket, id: "done", reference: "TCK-0099", state: "CLOSED_DELIVERED" },
        ]}
      />
    </MemoryRouter>,
  );
}

test("groups open requests with anything needing the requester first", () => {
  grouped();

  const headings = screen.getAllByRole("heading", { level: 3 }).map((item) => item.textContent);
  expect(headings).toEqual(["Needs your action1", "Drafts1", "With Istari1"]);
});

test("choosing a category shows it as one flat list without the archive", async () => {
  grouped();

  await userEvent.click(screen.getByRole("button", { name: /Needs your action/ }));

  expect(screen.queryByRole("heading", { level: 3 })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /TCK-0002/ })).toBeVisible();
  expect(screen.queryByRole("button", { name: /TCK-0001/ })).not.toBeInTheDocument();
  expect(screen.queryByText("Closed requests")).not.toBeInTheDocument();
});

test("the closed filter lists closed requests directly", async () => {
  grouped();

  await userEvent.click(screen.getByRole("button", { name: /^Closed/ }));

  expect(screen.getByRole("button", { name: /TCK-0099/ })).toBeVisible();
  expect(screen.queryByRole("button", { name: /TCK-0003/ })).not.toBeInTheDocument();
});

test("the chosen sort reorders the requests on show", async () => {
  grouped();

  await userEvent.click(screen.getByRole("button", { name: /All open/ }));
  await userEvent.selectOptions(screen.getByLabelText("Sort by"), "reference");

  // Scope to the open register: the collapsed archive is still in the document.
  const references = within(screen.getByRole("region", { name: "Your requests" }))
    .getAllByRole("button", { name: /TCK-/ })
    .map((item) => item.textContent?.slice(0, 8));
  expect(references).toEqual(["TCK-0002", "TCK-0001", "TCK-0003"]);
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
