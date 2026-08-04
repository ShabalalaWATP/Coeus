import {
  acceptAssignmentRecommendation,
  previewAssignmentRecommendation,
  type AssignmentRecommendation,
} from "./assignment-recommendations";

afterEach(() => vi.restoreAllMocks());

test("uses CSRF-protected preview and acceptance endpoints", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
  vi.stubGlobal("fetch", fetchMock);
  const recommendation = {
    recommendationId: "recommendation-1",
    previewHash: "a".repeat(64),
  } as AssignmentRecommendation;

  await previewAssignmentRecommendation(
    "ticket-1",
    {
      effortMinMinutes: 120,
      effortMaxMinutes: 240,
      deadline: "2026-08-10T17:00:00.000Z",
      capabilityIds: ["RFA-REGIONAL"],
      unitId: "team-1",
    },
    "csrf",
  );
  await acceptAssignmentRecommendation(
    "ticket-1",
    recommendation,
    "team-1",
    "analyst-1",
    "",
    "csrf",
  );

  expect(fetchMock.mock.calls[0]?.[0]).toContain("/assignment-recommendations/preview");
  expect(fetchMock.mock.calls[1]?.[0]).toContain("/assignment-recommendations/accept");
  expect(fetchMock.mock.calls[1]?.[1]).toEqual(
    expect.objectContaining({
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
      method: "POST",
    }),
  );
});
