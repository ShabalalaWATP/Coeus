import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { resetQueryClientForTests } from "../../app/query-client";
import type { AuthSession } from "../../lib/api-client/client";
import type { Ticket } from "../../lib/api-client/tickets";
import { baseTicket, fetchByUrl, renderRequests } from "../../test/requests-fixtures";
import { previewSession } from "../../test/test-utils";

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("shows a read-only workspace to tagged viewers", async () => {
  const viewerSession: AuthSession = {
    csrfToken: "test-csrf-token",
    user: { ...previewSession.user, id: "viewer-user", permissions: ["chat:use"] },
  };
  const sharedTicket: Ticket = {
    ...baseTicket,
    collaborators: [
      {
        userId: "viewer-user",
        username: "colleague@example.test",
        displayName: "Customer Colleague",
        access: "viewer",
        addedByUserId: "preview-user",
        createdAt: "2026-07-06T00:00:00Z",
      },
    ],
  };
  vi.stubGlobal("fetch", fetchByUrl([["/api/v1/tickets", { tickets: [sharedTicket] }]]));

  renderRequests("/app/requests/ticket-1", viewerSession);

  expect(await screen.findByText("The conversation is read-only for this request.")).toBeVisible();
  await userEvent.click(screen.getByText("Request history"));
  expect(screen.getByText("The timeline is read-only for this request.")).toBeVisible();
  expect(screen.queryByLabelText("Message")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Additional information")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Tag a user")).not.toBeInTheDocument();
  expect(screen.queryByText("Edit details manually")).not.toBeInTheDocument();
});
