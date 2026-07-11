import {
  addAnalystNote,
  assignAnalystTask,
  linkAnalystProduct,
  listAnalystCandidates,
  listAnalystTasks,
  saveDraftProduct,
  submitTaskForReview,
  updateWorkPackage,
} from "./analyst";
import { ApiError } from "./client";

afterEach(() => {
  vi.restoreAllMocks();
});

test("calls analyst workflow endpoints with CSRF-protected mutations", async () => {
  const task = { ticketId: "ticket-1" };
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(task),
  });
  vi.stubGlobal("fetch", fetchMock);

  await listAnalystTasks();
  await addAnalystNote("ticket-1", "Checked sources.", "csrf");
  await linkAnalystProduct("ticket-1", "product-1", "csrf");
  await updateWorkPackage("ticket-1", "package-1", "complete", "csrf");
  await saveDraftProduct(
    "ticket-1",
    {
      title: "Draft",
      summary: "Summary",
      productType: "finished_output",
      content: "MOCK DATA ONLY draft content.",
      assets: [],
    },
    "csrf",
  );
  await submitTaskForReview("ticket-1", "csrf");

  expect(fetchMock).toHaveBeenNthCalledWith(1, "http://127.0.0.1:8001/api/v1/analyst/tasks", {
    credentials: "include",
    method: "GET",
  });
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/analyst/tasks/ticket-1/notes",
    expect.objectContaining({
      body: JSON.stringify({ body: "Checked sources." }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
      method: "POST",
    }),
  );
  expect(fetchMock).toHaveBeenLastCalledWith(
    "http://127.0.0.1:8001/api/v1/analyst/tasks/ticket-1/submit",
    { credentials: "include", headers: { "X-CSRF-Token": "csrf" }, method: "POST" },
  );
});

test("lists analyst candidates and assigns tasks with CSRF protection", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ analysts: [] }),
  });
  vi.stubGlobal("fetch", fetchMock);

  await listAnalystCandidates("rfa");
  await assignAnalystTask(
    "ticket-1",
    ["analyst-1", "analyst-2"],
    "Maritime Assessment Cell",
    ["Validate scope"],
    "csrf",
  );

  expect(fetchMock).toHaveBeenNthCalledWith(
    1,
    "http://127.0.0.1:8001/api/v1/analyst/candidates?route=rfa",
    { credentials: "include", method: "GET" },
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/analyst/tasks/ticket-1/assign",
    expect.objectContaining({
      body: JSON.stringify({
        analystUserIds: ["analyst-1", "analyst-2"],
        teamName: "Maritime Assessment Cell",
        workPackages: ["Validate scope"],
      }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
      method: "POST",
    }),
  );
});

test("converts analyst API errors", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: () =>
        Promise.resolve({ error: { code: "draft_required", message: "Draft required." } }),
    }),
  );

  await expect(submitTaskForReview("ticket-1", "csrf")).rejects.toEqual(
    new ApiError(409, "draft_required", "Draft required."),
  );
});
