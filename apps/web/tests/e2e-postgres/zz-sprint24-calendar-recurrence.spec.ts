import { expect, type Page, test } from "@playwright/test";

import { ensureSyntheticOrganisation, login, logout } from "./sprint24-postgres-helpers";

const API_BASE_URL = "http://127.0.0.1:8022";
const privateNote = "Private weekly browser recurrence evidence";
const updatedNote = "Updated private weekly browser recurrence evidence";

type CalendarEvent = {
  activity: string;
  availability: string;
  cancelledAt: string | null;
  createdAt: string | null;
  createdByUserId: string;
  eventId: string;
  managerScopeUnitId: string | null;
  note: string;
  occurrenceKey?: string;
  ownerUserId: string;
  privacy: string;
  recurrence: { frequency: string; interval: number; until: string; weekdays: number[] } | null;
  duplicateSources?: string[];
  seriesEventId?: string;
  seriesTiming?: CalendarEvent["timing"];
  source: string;
  status: string;
  timing: {
    allDayEnd: string | null;
    allDayStart: string | null;
    endsAt: string | null;
    startsAt: string | null;
    timeZone: string;
  };
  updatedAt: string | null;
  version: number;
};

type Workspace = {
  planningGrantId: string | null;
  relationship: string;
  unit: { id: string; name: string };
};

test.beforeAll(async ({ browser }) => {
  const context = await browser.newContext();
  await ensureSyntheticOrganisation(await context.newPage());
  await context.close();
});

test("protects and updates a private weekly personal series end to end", async ({ page }) => {
  const dates = weeklyDates();

  await login(page, "rfa.team@example.test", "RFA Products");
  const workspaces = await apiGet<{ workspaces: Workspace[] }>(
    page,
    "/api/v1/organisation/workspaces",
  );
  const team = workspaces.workspaces.find((item) => item.unit.name === "RFA Assessment Team");
  expect(team?.relationship).toBe("home");
  expect(team?.planningGrantId).toBeTruthy();
  const capacityPath = capacityUrl(team!.unit.id, team!.planningGrantId!);
  const baselineCapacity = await apiGet<{ assignableMinutes: number }>(page, capacityPath);
  await logout(page);

  await login(page, "analyst@example.test", "Analyst Workbench");
  await page.goto("/account/calendar");
  await page.getByLabel("First day").fill(dates.first);
  await page.getByLabel("Last day").fill(dates.first);
  await page.getByLabel("Team visibility").selectOption("private");
  await page.getByLabel("Frequency").selectOption("weekly");
  await page.getByLabel("Repeat until").fill(dates.last);
  const checkedDay = page.getByRole("group", { name: "Repeat on" }).getByRole("checkbox", {
    checked: true,
  });
  if ((await checkedDay.count()) === 1) await checkedDay.uncheck();
  await page.getByLabel(dates.weekdayLabel).check();
  await page.getByLabel("Note (optional)").fill(privateNote);
  await page.getByRole("button", { name: "Add to calendar" }).click();
  await expect(agendaNote(page, privateNote)).toHaveCount(3);

  const ownerCalendar = await calendar(page, dates);
  const occurrences = ownerCalendar.events.filter((event) => event.note === privateNote);
  expect(occurrences.map((event) => event.occurrenceKey)).toEqual(dates.occurrences);
  const series = occurrences[0];
  expect(new Set(occurrences.map((event) => event.seriesEventId))).toEqual(
    new Set([series.seriesEventId]),
  );
  await logout(page);

  await login(page, "analyst.2@example.test", "Analyst Workbench");
  const otherCalendar = await calendar(page, dates);
  expect(otherCalendar.events.some((event) => event.seriesEventId === series.seriesEventId)).toBe(
    false,
  );
  const denied = await deniedMutation(page, series);
  // The body is the failure message: a refusal that turns into a schema error
  // should say which field broke rather than only that the status differed.
  expect(denied, denied.body).toMatchObject({ status: 403, code: "calendar_change_denied" });
  await logout(page);

  await login(page, "rfa.team@example.test", "RFA Products");
  const projectionPath = projectionUrl(team!.unit.id, dates);
  const projection = await apiGet<{ entries: Array<Record<string, unknown>> }>(
    page,
    projectionPath,
  );
  const projected = projection.entries.filter(
    (entry) => entry.seriesEventId === series.seriesEventId,
  );
  expect(projected).toHaveLength(dates.occurrences.length);
  expect(projected).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        activity: null,
        detail: "availability",
        eventId: null,
        note: null,
        ownerUserId: null,
      }),
    ]),
  );
  const unavailableCapacity = await apiGet<{ assignableMinutes: number }>(page, capacityPath);
  expect(unavailableCapacity.assignableMinutes).toBeLessThan(baselineCapacity.assignableMinutes);
  await logout(page);

  await login(page, "analyst@example.test", "Analyst Workbench");
  await page.goto("/account/calendar");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Edit Leave this occurrence" }).first().click();
  await page
    .locator("label")
    .filter({ hasText: /^Availability/ })
    .locator("select")
    .selectOption("available");
  await page.getByLabel("Note (optional)").fill(updatedNote);
  await page.getByRole("button", { name: "Save this occurrence" }).click();
  await expect(agendaNote(page, updatedNote)).toHaveCount(1);
  await expect(agendaNote(page, privateNote)).toHaveCount(2);

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Cancel Leave occurrence" }).nth(1).click();
  await expect(agendaNote(page, privateNote)).toHaveCount(1);

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Edit Leave this and future occurrences" }).nth(1).click();
  await page
    .locator("label")
    .filter({ hasText: /^Availability/ })
    .locator("select")
    .selectOption("available");
  await page.getByLabel("Note (optional)").fill(updatedNote);
  await page.getByRole("button", { name: "Save this and future occurrences" }).click();
  await expect(agendaNote(page, updatedNote)).toHaveCount(2);
  await expect(agendaNote(page, privateNote)).toHaveCount(0);

  const updated = (await calendar(page, dates)).events.filter(
    (event) => event.note === updatedNote,
  );
  expect(updated).toHaveLength(2);
  expect(updated.every((event) => event.availability === "available")).toBe(true);
  const updatedSeriesIds = new Set(updated.map((event) => event.seriesEventId));
  expect(updatedSeriesIds.size).toBe(2);
  await logout(page);

  await login(page, "rfa.team@example.test", "RFA Products");
  const editedProjection = await apiGet<{ entries: CalendarEvent[] }>(page, projectionPath);
  expect(
    editedProjection.entries
      .filter((entry) => updatedSeriesIds.has(entry.seriesEventId))
      .every((entry) => entry.availability === "available"),
  ).toBe(true);
  const editedCapacity = await apiGet<{ assignableMinutes: number }>(page, capacityPath);
  expect(editedCapacity.assignableMinutes).toBe(baselineCapacity.assignableMinutes);
  await logout(page);

  await login(page, "analyst@example.test", "Analyst Workbench");
  await page.goto("/account/calendar");
  for (const remaining of [1, 0]) {
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "Cancel Leave series" }).first().click();
    await expect(agendaNote(page, updatedNote)).toHaveCount(remaining);
  }
  expect(
    (await calendar(page, dates)).events.some(
      (event) => event.seriesEventId === series.seriesEventId,
    ),
  ).toBe(false);
  await logout(page);

  await login(page, "rfa.team@example.test", "RFA Products");
  const cancelledProjection = await apiGet<{ entries: CalendarEvent[] }>(page, projectionPath);
  expect(
    cancelledProjection.entries.some((entry) => updatedSeriesIds.has(entry.seriesEventId)),
  ).toBe(false);
  const restoredCapacity = await apiGet<{ assignableMinutes: number }>(page, capacityPath);
  expect(restoredCapacity.assignableMinutes).toBe(baselineCapacity.assignableMinutes);
});

test("calendar modes remain keyboard-operable at a narrow mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, "analyst@example.test", "Analyst Workbench");
  await page.goto("/account/calendar");
  const tabs = page.getByRole("tablist", { name: "Calendar view" });
  await expect(tabs).toBeVisible();
  const agenda = page.getByRole("tab", { name: "Agenda" });
  await expect(agenda).toHaveAttribute("aria-selected", "true");
  await agenda.focus();
  await agenda.press("ArrowRight");
  // Assert the selected mode rather than the panel being visible: the panel is
  // the activity list itself, so it collapses to nothing whenever the chosen
  // window holds no events, which has nothing to do with keyboard operability.
  await expect(page.getByRole("tab", { name: "Month" })).toBeFocused();
  await expect(page.getByRole("tab", { name: "Month" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tabpanel", { name: "month calendar activity" })).toHaveCount(1);
  await page.getByRole("tab", { name: "Month" }).press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Week" })).toBeFocused();
  await expect(page.getByRole("tab", { name: "Week" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tabpanel", { name: "week calendar activity" })).toHaveCount(1);
});

async function apiGet<T>(page: Page, path: string): Promise<T> {
  return page.evaluate(
    async ({ base, requestPath }) => {
      const response = await fetch(`${base}${requestPath}`, { credentials: "include" });
      if (!response.ok) throw new Error(`GET ${requestPath} returned ${response.status}`);
      return (await response.json()) as T;
    },
    { base: API_BASE_URL, requestPath: path },
  );
}

function agendaNote(page: Page, note: string) {
  // Scope by the agenda region's accessible name. Walking up from the heading
  // breaks whenever the heading gains a wrapper, which is what happened here.
  return page.getByRole("region", { name: "Your activity" }).getByText(new RegExp(note));
}

async function calendar(page: Page, dates: ReturnType<typeof weeklyDates>) {
  return apiGet<{ events: CalendarEvent[] }>(
    page,
    `/api/v1/calendar/me?windowStart=${encodeURIComponent(`${dates.first}T00:00:00Z`)}` +
      `&windowEnd=${encodeURIComponent(`${addDays(dates.last, 1)}T00:00:00Z`)}`,
  );
}

async function deniedMutation(page: Page, occurrence: CalendarEvent) {
  return page.evaluate(
    async ({ base, item }) => {
      const session = (await (
        await fetch(`${base}/api/v1/auth/me`, { credentials: "include" })
      ).json()) as {
        csrfToken: string;
      };
      // The occurrence response carries fields the mutation schema forbids, so
      // every one of them has to go or the request fails validation before the
      // authority check this test exists to prove.
      const event = { ...item, timing: item.seriesTiming ?? item.timing };
      delete event.occurrenceKey;
      delete event.seriesEventId;
      delete event.seriesTiming;
      delete event.duplicateSources;
      const response = await fetch(`${base}/api/v1/calendar/previews`, {
        body: JSON.stringify({
          operation: "update",
          event,
          expectedVersion: event.version,
          authorisingGrantId: null,
          reason: "Attempt to update another user's private series.",
        }),
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": session.csrfToken },
        method: "POST",
      });
      const body = (await response.json()) as { error?: { code?: string } };
      return {
        body: JSON.stringify(body).slice(0, 900),
        code: body.error?.code,
        status: response.status,
      };
    },
    { base: API_BASE_URL, item: occurrence },
  );
}

function capacityUrl(unitId: string, grantId: string) {
  const start = new Date();
  start.setUTCHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setUTCDate(end.getUTCDate() + 7);
  return (
    `/api/v1/organisation/workspaces/${unitId}/capacity?authorisingGrantId=${grantId}` +
    `&windowStart=${encodeURIComponent(start.toISOString())}&windowEnd=${encodeURIComponent(end.toISOString())}`
  );
}

function projectionUrl(unitId: string, dates: ReturnType<typeof weeklyDates>) {
  return (
    `/api/v1/calendar/units/${unitId}?windowStart=${encodeURIComponent(`${dates.first}T00:00:00Z`)}` +
    `&windowEnd=${encodeURIComponent(`${addDays(dates.first, 14)}T23:59:59Z`)}` +
    "&includeDescendants=false&view=availability"
  );
}

function weeklyDates() {
  const first = new Date();
  first.setUTCHours(12, 0, 0, 0);
  do first.setUTCDate(first.getUTCDate() + 1);
  while (first.getUTCDay() === 0 || first.getUTCDay() === 6);
  const firstIso = first.toISOString().slice(0, 10);
  const last = addDays(firstIso, 14);
  const weekday = first.getUTCDay() === 0 ? 6 : first.getUTCDay() - 1;
  return {
    first: firstIso,
    last,
    occurrences: [firstIso, addDays(firstIso, 7), last],
    weekdayLabel: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][
      weekday
    ],
  };
}

function addDays(value: string, days: number) {
  const date = new Date(`${value}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}
