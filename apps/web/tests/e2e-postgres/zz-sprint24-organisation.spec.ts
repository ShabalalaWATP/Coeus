import { expect, test } from "@playwright/test";

import {
  ensureSyntheticOrganisation,
  fetchStatus,
  login,
  logout,
} from "./sprint24-postgres-helpers";

test.beforeAll(async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  await ensureSyntheticOrganisation(page);
  await context.close();
});

test("shows a read-only cutover decision with external evidence blockers", async ({ page }) => {
  await login(page, "admin@example.test", "Admin");
  const response = page.waitForResponse((item) =>
    item.url().endsWith("/api/v1/admin/organisation/cutover-readiness"),
  );
  await page.goto("/admin/organisation");
  const readiness = await response;
  expect(readiness.request().method()).toBe("GET");
  await expect(page.getByText("Read-only readiness check", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Not ready to change services" })).toBeVisible();
  await expect(page.getByText("User journeys have been checked", { exact: true })).toBeVisible();
  await expect(page.getByText("Automated checks have passed", { exact: true })).toBeVisible();
  await expect(page.getByText("Security checks have passed", { exact: true })).toBeVisible();
  await expect(page.getByText("Operational routing is unchanged", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /activate|change service/i })).toHaveCount(0);
});

test("keeps an ordinary user's private canonical calendar private", async ({ page }) => {
  const privateNote = "Private customer calendar evidence";
  await login(page, "user@example.test", "My Requests");
  await page.goto("/account/calendar");
  await expect(page.getByRole("heading", { name: "My calendar" })).toBeVisible();
  await page.getByLabel("Team visibility").selectOption("private");
  await page.getByLabel("Note (optional)").fill(privateNote);
  await page.getByRole("button", { name: "Add to calendar" }).click();
  await expect(page.getByText(new RegExp(privateNote))).toBeVisible();
  await logout(page);

  await login(page, "colleague@example.test", "My Requests");
  await page.goto("/account/calendar");
  await expect(page.getByRole("heading", { name: "My calendar" })).toBeVisible();
  await expect(page.getByText(new RegExp(privateNote))).toHaveCount(0);
});

test("shows the analyst's canonical My Work projection", async ({ page }) => {
  await login(page, "analyst@example.test", "Analyst Workbench");
  await page.goto("/account/profile");
  const myWork = page.getByRole("heading", { name: "My work" }).locator("..").locator("..");
  await expect(myWork).toContainText("EXR-2002");
  await expect(myWork).toContainText("North Sea shipping pattern assessment");
  await expect(myWork.getByRole("link", { name: /Assess available evidence/ })).toBeVisible();
});

test("gives the direct delivery manager board, forecast and planning access", async ({ page }) => {
  await login(page, "rfa.team@example.test", "RFA Products");
  await page.goto("/teams");
  const workspace = page.getByLabel("Organisation workspace", { exact: true });
  await expect(workspace.getByRole("heading", { name: "RFA Assessment Team" })).toBeVisible();
  await page.getByRole("tab", { name: "Board" }).click();
  await expect(page.getByRole("heading", { name: "Team task board" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Next 7 days" })).toBeVisible();
  const taskCard = page.getByRole("listitem").filter({ hasText: /\bEXR-2002\b/ });
  await expect(taskCard).toContainText("RFA Assessment Team");
  const plan = taskCard.getByRole("button", { name: "Plan work" });
  await expect(plan).toBeVisible();
  await plan.click();
  await expect(page.getByRole("heading", { name: /Plan Assess available evidence/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Review plan" })).toBeVisible();
});

test("suppresses small ancestor counts and denies named calendar detail", async ({ page }) => {
  await login(page, "rfa.manager@example.test", "RFA Queue");
  const workspaceResponse = page.waitForResponse((item) =>
    item.url().endsWith("/api/v1/organisation/workspaces"),
  );
  await page.goto("/teams");
  const workspaces = (await (await workspaceResponse).json()) as {
    workspaces: Array<{ canViewDetail: boolean; unit: { id: string; shortName: string } }>;
  };
  const rfa = workspaces.workspaces.find((item) => item.unit.shortName === "RFA");
  expect(rfa).toBeDefined();
  expect(rfa?.canViewDetail).toBe(false);
  await page.getByRole("tab", { name: "Calendar" }).click();
  // The calendar is collapsed until asked for, so its controls only exist once
  // the panel has been opened.
  await page.getByRole("button", { name: "Open team calendar" }).click();
  await page.getByLabel("Include child units").check();
  await expect(
    page.getByText("Small totals are hidden to protect individual availability."),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Request detailed view" })).toHaveCount(0);

  const start = new Date().toISOString();
  const end = new Date(Date.now() + 14 * 86_400_000).toISOString();
  const detail = await fetchStatus(
    page,
    `/api/v1/calendar/units/${rfa!.unit.id}?windowStart=${encodeURIComponent(start)}` +
      `&windowEnd=${encodeURIComponent(end)}&includeDescendants=false&view=detail`,
  );
  // Calendar scope denial is deliberately non-enumerating.
  expect(detail.status).toBe(404);
});

test("keeps JIOC oversight aggregate-only with no named assignment authority", async ({ page }) => {
  await login(page, "jioc.team@example.test", "JIOC Oversight");
  const workspaceResponse = page.waitForResponse((item) =>
    item.url().endsWith("/api/v1/organisation/workspaces"),
  );
  await page.goto("/teams");
  const workspaces = (await (await workspaceResponse).json()) as {
    workspaces: Array<{
      canViewDetail: boolean;
      canViewTasks: boolean;
      planningGrantId: string | null;
      unit: { shortName: string };
    }>;
  };
  const jioc = workspaces.workspaces.find((item) => item.unit.shortName === "JIOC");
  expect(jioc).toMatchObject({
    canViewDetail: false,
    canViewTasks: true,
    planningGrantId: null,
  });
  await expect(page.getByRole("heading", { name: "Team task board" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Plan work" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Next 7 days" })).toHaveCount(0);
});

test("leaves the established QC queue available after organisation setup", async ({ page }) => {
  await login(page, "qc.manager@example.test", "QC Queue");
  const queue = await fetchStatus(page, "/api/v1/qc/queue");
  expect(queue.status).toBe(200);
  await expect(page.getByRole("heading", { name: "QC Queue" })).toBeVisible();
});
