import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { resetQueryClientForTests } from "../../app/query-client";
import type { AuthSession } from "../../lib/api-client/auth";
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

test("keeps editor intake controls without granting submission authority", async () => {
  const editorSession: AuthSession = {
    csrfToken: "test-csrf-token",
    user: {
      ...previewSession.user,
      id: "editor-user",
      permissions: ["chat:use", "ticket:add_information"],
    },
  };
  const sharedTicket: Ticket = {
    ...baseTicket,
    collaborators: [
      {
        userId: "editor-user",
        username: "editor@example.test",
        displayName: "Request Editor",
        access: "editor",
        addedByUserId: "preview-user",
        createdAt: "2026-07-06T00:00:00Z",
      },
    ],
  };
  vi.stubGlobal("fetch", fetchByUrl([["/api/v1/tickets", { tickets: [sharedTicket] }]]));

  renderRequests("/app/requests/ticket-1", editorSession);

  const details = await screen.findByText("Edit details manually");
  await userEvent.click(details);

  expect(screen.getByRole("button", { name: "Save" })).toBeVisible();
  expect(screen.queryByRole("button", { name: "Submit" })).not.toBeInTheDocument();
});

test("does not treat global write authority as submission authority", async () => {
  const writerSession: AuthSession = {
    csrfToken: "test-csrf-token",
    user: {
      ...previewSession.user,
      id: "global-writer",
      permissions: ["ticket:read_all", "ticket:write_all"],
    },
  };
  vi.stubGlobal("fetch", fetchByUrl([["/api/v1/tickets", { tickets: [baseTicket] }]]));

  renderRequests("/app/requests/ticket-1", writerSession);

  const details = await screen.findByText("Edit details manually");
  await userEvent.click(details);
  expect(screen.getByRole("button", { name: "Save" })).toBeVisible();
  expect(screen.queryByRole("button", { name: "Submit" })).not.toBeInTheDocument();
});

test("offers a read-only submit control for explicit transition authority", async () => {
  const transitionSession: AuthSession = {
    csrfToken: "test-csrf-token",
    user: {
      ...previewSession.user,
      id: "transition-reviewer",
      permissions: ["ticket:read_all", "ticket:transition"],
    },
  };
  const readyTicket: Ticket = {
    ...baseTicket,
    isReadyForSubmission: true,
    intake: { ...baseTicket.intake, missingInformation: [] },
  };
  vi.stubGlobal("fetch", fetchByUrl([["/api/v1/tickets", { tickets: [readyTicket] }]]));

  renderRequests("/app/requests/ticket-1", transitionSession);

  expect(await screen.findByRole("button", { name: "Submit" })).toBeEnabled();
  expect(screen.queryByText("Edit details manually")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
});
