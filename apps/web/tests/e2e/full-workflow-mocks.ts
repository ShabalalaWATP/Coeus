import type { Page, Route } from "@playwright/test";

import {
  acg,
  analystTask,
  type FlowState,
  qcProduct,
  routingQueue,
  routingTicket,
  session,
  ticket,
} from "./full-workflow-data";

export { createFlowState, type FlowState } from "./full-workflow-data";

const API = "http://127.0.0.1:8011/api/v1";

export async function installApiMocks(page: Page, flow: FlowState) {
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");
    const method = request.method();

    if (method === "GET" && path === "/auth/me") return json(route, session());
    if (method === "GET" && path === "/notifications") {
      return json(route, { notifications: [], unread: 0 });
    }
    if (method === "GET" && path === "/feedback/requests") return json(route, { requests: [] });
    if (method === "GET" && path === "/users/directory") return json(route, { users: [] });
    if (method === "GET" && path === "/tickets") {
      return json(route, { tickets: flow.ticketCreated ? [ticket(flow)] : [] });
    }
    if (method === "POST" && path === "/chat/messages") {
      flow.ticketCreated = true;
      flow.stage = "draft";
      return json(route, ticket(flow), 201);
    }
    if (method === "POST" && path === "/tickets/ticket-e2e/submit") {
      flow.stage = "route";
      return json(route, ticket(flow, "RFI_SEARCHING"));
    }
    if (method === "GET" && path === "/routing/rfa/queue") {
      return json(route, routingQueue(flow, "queue"));
    }
    if (method === "GET" && path === "/routing/rfa/release-queue") {
      return json(route, routingQueue(flow, "release"));
    }
    if (method === "POST" && path === "/routing/ticket-e2e/run") {
      flow.stage = "review";
      return json(route, routingTicket(flow));
    }
    if (method === "POST" && path === "/routing/ticket-e2e/approve") {
      flow.stage = "assignment";
      return json(route, routingTicket(flow));
    }
    if (method === "GET" && path === "/analyst/candidates") {
      return json(route, {
        analysts: [{ displayName: "Analyst Operator", userId: "analyst-user", username: "a.test" }],
      });
    }
    if (method === "POST" && path === "/analyst/tasks/ticket-e2e/assign") {
      flow.stage = "analyst";
      return json(route, analystTask(flow));
    }
    if (method === "GET" && path === "/analyst/tasks") {
      return json(route, { tasks: flow.stage === "analyst" ? [analystTask(flow)] : [] });
    }
    if (method === "PATCH" && path.includes("/work-packages/package-1")) {
      flow.workPackageDone = true;
      return json(route, analystTask(flow));
    }
    if (method === "POST" && path === "/analyst/tasks/ticket-e2e/drafts") {
      flow.draftSaved = true;
      return json(route, analystTask(flow));
    }
    if (method === "POST" && path === "/analyst/tasks/ticket-e2e/submit-qc") {
      flow.stage = "qc";
      return json(route, analystTask(flow, "QC_REVIEW"));
    }
    if (method === "GET" && path === "/qc/queue")
      return json(route, { products: [qcProduct(flow)] });
    if (method === "GET" && path === "/acgs") return json(route, { acgs: [acg] });
    if (method === "POST" && path === "/qc/products/ticket-e2e/approve") {
      flow.stage = "release";
      return json(route, qcProduct(flow));
    }
    if (method === "POST" && path === "/routing/ticket-e2e/release") {
      flow.released = true;
      return json(route, routingTicket(flow, "DISSEMINATION_READY"));
    }
    return json(route, {});
  });
}

async function json(route: Route, payload: unknown, status = 200) {
  await route.fulfill({ contentType: "application/json", json: payload, status });
}
