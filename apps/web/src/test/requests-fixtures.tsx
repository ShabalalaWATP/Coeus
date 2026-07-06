import { render, type RenderResult } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { previewSession } from "./test-utils";
import { AppProviders } from "../app/providers";
import RequestsPage from "../features/requests/RequestsPage";
import type { AuthSession } from "../lib/api-client/client";
import type { Ticket } from "../lib/api-client/tickets";

export const baseTicket: Ticket = {
  id: "ticket-1",
  reference: "TCK-0001",
  requesterUserId: "preview-user",
  state: "INFO_REQUIRED",
  intake: {
    title: "Baltic Ports Brief",
    description: "Assess mock port activity.",
    operationalQuestion: "What activity needs attention?",
    areaOrRegion: "Baltic ports",
    timePeriodStart: null,
    timePeriodEnd: null,
    priority: null,
    deadline: null,
    requiredOutputFormat: "Briefing note",
    knownContext: null,
    restrictionsOrCaveats: null,
    customerSuccessCriteria: null,
    suggestedProjectName: null,
    suggestedAcgContext: null,
    missingInformation: ["priority", "customer_success_criteria"],
    confidence: 0.71,
  },
  isReadyForSubmission: false,
  suggestedProjectName: null,
  visibleProductMatches: [],
  collaborators: [],
  messages: [
    {
      id: "message-1",
      author: "user",
      body: "Need a Baltic ports brief.",
      createdAt: "2026-07-05T00:00:00Z",
    },
    {
      id: "message-2",
      author: "assistant",
      body: "I need priority and success criteria.",
      createdAt: "2026-07-05T00:00:01Z",
    },
  ],
  attachments: [],
  agentRuns: [],
  timeline: [
    {
      id: "timeline-1",
      eventType: "ticket_created",
      body: "Draft intake started.",
      actorUserId: "preview-user",
      createdAt: "2026-07-05T00:00:00Z",
    },
  ],
  createdAt: "2026-07-05T00:00:00Z",
  updatedAt: "2026-07-05T00:00:01Z",
};

export const directory = {
  users: [
    {
      id: "colleague-1",
      username: "colleague@example.test",
      displayName: "Customer Colleague",
    },
  ],
};

export const rfiSearchResults = {
  ticketId: "ticket-1",
  ticketState: "RFI_MATCH_OFFERED",
  metrics: {
    runId: "run-1",
    query: "Regional Stability Brief Baltic ports",
    candidateCount: 1,
    offeredCount: 1,
    rejectedCount: 0,
    acceptedProductId: null,
    createdAt: "2026-07-05T00:02:00Z",
  },
  offers: [
    {
      productId: "product-1",
      title: "Existing Baltic Port Assessment",
      summary: "MOCK DATA ONLY reusable assessment.",
      productType: "assessment_report",
      matchScore: 0.82,
      matchReasons: ["full-text:baltic", "metadata:region"],
      classificationLevel: 2,
      releasability: ["MOCK"],
      region: "Baltic ports",
      timePeriodStart: null,
      timePeriodEnd: null,
      assetTypes: ["pdf"],
      offerableToUser: true,
      status: "offered",
      rejectionReason: null,
    },
  ],
};

type JsonByUrl = Array<[matcher: string, payload: unknown]>;

export function fetchByUrl(routes: JsonByUrl) {
  return vi.fn((url: string) => {
    const match = routes.find(([matcher]) => url.includes(matcher));
    return Promise.resolve({
      ok: match !== undefined,
      status: match === undefined ? 404 : 200,
      json: () =>
        Promise.resolve(match?.[1] ?? { error: { code: "not_found", message: "Missing." } }),
    });
  });
}

export function renderRequests(
  initialPath: string,
  session: AuthSession | null = previewSession,
): RenderResult {
  window.history.pushState({}, "Test page", initialPath);
  return render(
    <AppProviders initialAuthSession={session}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/app/requests" element={<RequestsPage />} />
          <Route path="/app/requests/new" element={<RequestsPage />} />
          <Route path="/app/requests/:ticketId" element={<RequestsPage />} />
        </Routes>
      </MemoryRouter>
    </AppProviders>,
  );
}
