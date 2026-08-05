import { screen } from "@testing-library/react";

import { ProfileCalendarSnapshot } from "./ProfileCalendarSnapshot";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => resetQueryClientForTests());
afterEach(() => vi.restoreAllMocks());

test("summarises the signed-in user's next seven days", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          events: [
            {
              eventId: "event-1",
              activity: "duty",
              availability: "unavailable",
              timing: { allDayStart: "2026-08-04", startsAt: null },
            },
          ],
        }),
    }),
  );

  renderWithProviders(<ProfileCalendarSnapshot />);

  expect(await screen.findByText("duty")).toBeVisible();
  expect(screen.getByRole("link", { name: "Open calendar" })).toHaveAttribute(
    "href",
    "/account/calendar",
  );
});

test("uses a bounded message while canonical calendars are unavailable", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: () => Promise.resolve({ error: { code: "unavailable", message: "Unavailable." } }),
    }),
  );

  renderWithProviders(<ProfileCalendarSnapshot />);

  expect(await screen.findByRole("alert")).toHaveTextContent("Your calendar is not available yet.");
});
