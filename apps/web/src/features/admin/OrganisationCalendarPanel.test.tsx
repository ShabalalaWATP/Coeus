import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { OrganisationCalendarPanel } from "./OrganisationCalendarPanel";
import { resetQueryClientForTests } from "../../app/query-client";
import type { OrganisationUnit } from "../../lib/api-client/organisation-admin";
import { renderWithProviders } from "../../test/test-utils";

const unit = {
  id: "d571f68e-82c6-4fa6-925f-dcba6a911d61",
  name: "Synthetic Analysis Team",
  shortName: "SAT",
  category: "delivery_team",
  parentId: null,
  timeZone: "Europe/London",
  description: "Synthetic unit.",
  isActive: true,
  version: 1,
  validFrom: "2026-08-03T00:00:00Z",
  validUntil: null,
} satisfies OrganisationUnit;

function response(overrides: Record<string, unknown> = {}) {
  return {
    rootUnitId: unit.id,
    scope: "direct",
    generatedAt: "2026-08-03T10:00:00Z",
    unitIds: [unit.id],
    memberCount: 8,
    suppressed: false,
    truncated: false,
    entries: [
      {
        unitId: unit.id,
        timing: {
          timeZone: "Europe/London",
          startsAt: null,
          endsAt: null,
          allDayStart: "2026-08-05",
          allDayEnd: "2026-08-06",
        },
        availability: "unavailable",
        detail: "availability",
        eventId: null,
        ownerUserId: null,
        activity: null,
        note: null,
      },
    ],
    aggregates: [],
    ...overrides,
  };
}

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("shows coarse direct-team availability without identity", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(response()),
    }),
  );

  renderWithProviders(<OrganisationCalendarPanel unit={unit} />);
  await userEvent.click(screen.getByRole("button", { name: "Open team calendar" }));

  expect(await screen.findByText("Team member")).toBeVisible();
  expect(screen.getByText("Unavailable")).toBeVisible();
  expect(screen.getByText("5 Aug · all day")).toBeVisible();
});

test("switches to a privacy-explained descendant aggregate", async () => {
  const fetchMock = vi.fn((url: string) =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve(
          url.includes("includeDescendants=true")
            ? response({
                scope: "descendants",
                memberCount: null,
                suppressed: true,
                entries: [],
                aggregates: [
                  {
                    unitId: unit.id,
                    day: "2026-08-05",
                    memberCount: null,
                    unavailableCount: null,
                    suppressed: true,
                  },
                ],
              })
            : response(),
        ),
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<OrganisationCalendarPanel unit={unit} />);
  await userEvent.click(screen.getByRole("button", { name: "Open team calendar" }));
  await screen.findByText("Team member");
  await userEvent.click(screen.getByLabelText("Include child units"));

  expect(await screen.findByText("Fewer than 5")).toBeVisible();
  expect(
    screen.getByText("Small totals are hidden to protect individual availability."),
  ).toBeVisible();
  expect(screen.getByText("Private")).toBeVisible();
  expect(fetchMock).toHaveBeenLastCalledWith(
    expect.stringContaining("includeDescendants=true"),
    expect.objectContaining({ method: "GET" }),
  );
});

test("a large descendant cohort shows real counts and no privacy notice", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve(
            url.includes("includeDescendants=true")
              ? response({
                  scope: "descendants",
                  memberCount: 42,
                  suppressed: false,
                  entries: [],
                  aggregates: [
                    {
                      unitId: unit.id,
                      day: "2026-08-05",
                      memberCount: 42,
                      unavailableCount: 7,
                      suppressed: false,
                    },
                  ],
                })
              : response(),
          ),
      }),
    ),
  );

  renderWithProviders(<OrganisationCalendarPanel unit={unit} />);
  await userEvent.click(screen.getByRole("button", { name: "Open team calendar" }));
  await screen.findByText("Team member");
  await userEvent.click(screen.getByLabelText("Include child units"));

  expect(await screen.findByText("42")).toBeVisible();
  expect(await screen.findByText("7 unavailable")).toBeVisible();
  expect(
    screen.queryByText("Small totals are hidden to protect individual availability."),
  ).not.toBeInTheDocument();
});

test("makes detailed access explicit and handles a safe denial", async () => {
  const fetchMock = vi.fn((url: string) =>
    Promise.resolve(
      url.includes("view=detail")
        ? {
            ok: false,
            status: 404,
            json: () =>
              Promise.resolve({
                error: { code: "calendar_not_found", message: "Calendar not found." },
              }),
          }
        : { ok: true, status: 200, json: () => Promise.resolve(response()) },
    ),
  );
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<OrganisationCalendarPanel unit={unit} />);
  await userEvent.click(screen.getByRole("button", { name: "Open team calendar" }));
  await screen.findByText("Team member");
  await userEvent.click(screen.getByRole("button", { name: "Request detailed view" }));

  expect(
    await screen.findByText(
      "This calendar is unavailable or you do not have the required authority.",
    ),
  ).toBeVisible();
  expect(fetchMock).toHaveBeenLastCalledWith(
    expect.stringContaining("view=detail"),
    expect.objectContaining({ method: "GET" }),
  );
});

test("renders named timed detail and can close the calendar", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve(
          response({
            entries: [
              {
                unitId: unit.id,
                timing: {
                  timeZone: "Europe/London",
                  startsAt: "2026-08-05T10:00:00Z",
                  endsAt: "2026-08-05T11:00:00Z",
                  allDayStart: null,
                  allDayEnd: null,
                },
                availability: "partial",
                detail: "detail",
                eventId: "ba5dcfe7-d12c-4fe0-981c-77bd69057809",
                ownerUserId: "905e7f17-8d78-4b20-8ed6-42c7fe8b7483",
                activity: "training",
                note: null,
              },
            ],
          }),
        ),
    }),
  );

  renderWithProviders(<OrganisationCalendarPanel unit={unit} />);
  await userEvent.click(screen.getByRole("button", { name: "Open team calendar" }));

  expect(await screen.findByText("Named team member")).toBeVisible();
  expect(screen.getByText("training")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Close team calendar" }));
  expect(screen.queryByLabelText("Direct team availability")).not.toBeInTheDocument();
});

test("explains a direct period with no entries", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(response({ entries: [] })),
    }),
  );

  renderWithProviders(<OrganisationCalendarPanel unit={unit} />);
  await userEvent.click(screen.getByRole("button", { name: "Open team calendar" }));

  expect(await screen.findByText("No availability entries in this period.")).toBeVisible();
});

test("creates a canonical team-scoped event with the exact management grant", async () => {
  let previewPayload: Record<string, unknown> | undefined;
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (url.endsWith("/calendar/previews")) {
      if (typeof init?.body !== "string") throw new Error("Expected JSON request body");
      const parsed: unknown = JSON.parse(init.body);
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
        throw new Error("Expected an object request body");
      }
      previewPayload = parsed as Record<string, unknown>;
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ request: previewPayload, previewHash: "a".repeat(64) }),
      });
    }
    if (url.endsWith("/calendar/commands")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ eventId: "event", version: 1, replayed: false }),
      });
    }
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve(response({ entries: [] })),
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(
    <OrganisationCalendarPanel
      csrfToken="csrf"
      currentUserId="905e7f17-8d78-4b20-8ed6-42c7fe8b7483"
      managementGrantId="ba5dcfe7-d12c-4fe0-981c-77bd69057809"
      unit={unit}
    />,
  );
  await userEvent.click(screen.getByRole("button", { name: "Open team calendar" }));
  await screen.findByRole("heading", { name: "Add team event" });
  await userEvent.selectOptions(screen.getByLabelText("Activity"), "training");
  await userEvent.type(screen.getByLabelText("Shared detail"), "Synthetic team course");
  await userEvent.click(screen.getByRole("button", { name: "Add team event" }));
  expect(previewPayload).toBeDefined();
  expect(previewPayload?.event).toMatchObject({
    source: "team",
    managerScopeUnitId: unit.id,
    activity: "training",
  });
  expect(previewPayload?.authorisingGrantId).toBe("ba5dcfe7-d12c-4fe0-981c-77bd69057809");
});
