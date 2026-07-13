import { expect, type Page, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

const PASSWORD = "CoeusLocal1!";
const assessmentTitle = "North Atlantic Assessment";
let reference = "";

test.describe.configure({ mode: "serial" });

async function login(page: Page, username: string, heading: string) {
  await page.goto("/");
  await page.getByLabel("Username").fill(username);
  await page.getByRole("textbox", { name: "Password" }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in to Istari" }).click();
  await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
}

async function logout(page: Page) {
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in", exact: true })).toBeVisible();
}

test("denies an unrelated same-ACG user access to a PostgreSQL draft", async ({ page }) => {
  await login(page, "store.manager@example.test", "Intelligence Store");
  await page.goto("/store/upload");
  await page
    .getByRole("textbox", { name: "Title", exact: true })
    .fill("PostgreSQL draft isolation proof");
  await page
    .getByRole("textbox", { name: "Summary", exact: true })
    .fill("Synthetic draft visible only to its audience.");
  await page
    .getByRole("textbox", { name: "Description", exact: true })
    .fill("Synthetic browser security evidence.");
  await page.getByRole("textbox", { name: "Region", exact: true }).fill("North Atlantic");
  await page.getByRole("textbox", { name: "Tags", exact: true }).fill("synthetic,playwright");
  await page.getByRole("textbox", { name: "Source type", exact: true }).fill("synthetic-browser");
  await page.getByRole("combobox", { name: "Status", exact: true }).selectOption("draft");
  await page
    .getByRole("combobox", { name: "ACG", exact: true })
    .selectOption({ label: "ACG-EU-CYBER" });
  await page.getByLabel("Asset file", { exact: true }).setInputFiles({
    name: "draft-proof.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("MOCK DATA ONLY\nDraft byte evidence\n"),
  });
  await page.getByRole("button", { name: "Register product" }).click();
  await expect(page.getByText(/Created .*PostgreSQL draft isolation proof/)).toBeVisible();
  await logout(page);

  await login(page, "colleague@example.test", "My Requests");
  await page.goto("/store");
  await page
    .getByPlaceholder("Search title, summary, tags")
    .fill("PostgreSQL draft isolation proof");
  await page.getByRole("button", { name: "Search products" }).click();
  await expect(page.getByText("PostgreSQL draft isolation proof")).toHaveCount(0);
});

test("creates and submits a customer request through PostgreSQL", async ({ page }) => {
  await login(page, "user@example.test", "My Requests");
  await page.getByRole("button", { name: "Open new request" }).click();
  await page.getByLabel("Message").fill("Need a synthetic North Atlantic maritime assessment.");
  await page.getByRole("button", { name: "Send" }).click();
  reference =
    (await page
      .getByText(/^TCK-\d+$/)
      .first()
      .textContent()) ?? "";
  expect(reference).toMatch(/^TCK-\d+$/);
  await page.getByText("Edit details manually").click();
  const intake: Record<string, string> = {
    Title: "North Atlantic maritime assessment",
    Description: "Assess synthetic maritime activity and likely implications.",
    "Operational question": "What synthetic activity is occurring and why does it matter?",
    "Area or region": "North Atlantic",
    "Time period start": "2026-07-01",
    "Time period end": "2026-07-12",
    Priority: "routine",
    "Supported operation": "Synthetic maritime assurance",
    "Why it is urgent": "Required for a synthetic planning cycle.",
    "Latest useful time": "2026-07-20",
    "Requesting unit": "Synthetic Joint Team",
    Disciplines: "OSINT",
    "Output format": "Written assessment",
    "Success criteria": "Clear synthetic findings and caveats.",
  };
  for (const [label, value] of Object.entries(intake)) {
    await page.getByLabel(label, { exact: true }).fill(value);
  }
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Missing").locator("..")).toContainText("None");
  await page.getByRole("button", { name: "Submit", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Request journey" })).toBeVisible();
  await page.getByLabel("Close journey").click();
  await page.getByRole("button", { name: "Run search" }).click();
  await page.getByRole("button", { name: "Yes, task as new request" }).click();
  await expect(page.getByText("JIOC review", { exact: true })).toBeVisible();
});

test("routes the request as the JIOC user", async ({ page }) => {
  await login(page, "jioc.team@example.test", "JIOC Queue");
  await page.getByRole("button", { name: new RegExp(reference) }).click();
  await page.getByRole("button", { name: "Run capability checks" }).click();
  await expect(page.getByText(/Recommended route:/)).toBeVisible();
  await page.getByRole("button", { name: "Approve route" }).click();
  await expect(page.getByText("No tickets in this queue.")).toBeVisible();
});

test("assigns the request as the RFA manager", async ({ page }) => {
  await login(page, "rfa.manager@example.test", "RFA Queue");
  await page.getByRole("button", { name: new RegExp(reference) }).click();
  await page.getByRole("checkbox", { name: "Analyst", exact: true }).check();
  await page.getByRole("button", { name: "Assign analysts" }).click();
  await expect(page.getByText("No tickets in this queue.")).toBeVisible();
});

test("creates a controlled draft as the assigned analyst", async ({ page }) => {
  await login(page, "analyst@example.test", "Analyst Workbench");
  await page.getByRole("link", { name: new RegExp(reference) }).click();
  const workPackages = page
    .getByRole("region", { name: "Analyst task detail" })
    .getByRole("checkbox");
  for (let index = 0; index < (await workPackages.count()); index += 1) {
    const checkbox = workPackages.nth(index);
    await checkbox.click();
    await expect(checkbox).toBeChecked();
  }
  await page.getByLabel("Title", { exact: true }).fill(assessmentTitle);
  await page.getByLabel("Summary", { exact: true }).fill("Synthetic assessment summary.");
  await page
    .getByLabel("Content", { exact: true })
    .fill("Synthetic assessment content for controlled QC review.");
  await page.getByLabel("Mock supporting asset name").fill("assessment.txt");
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText(`v1: ${assessmentTitle}`)).toBeVisible();
  await page.getByRole("button", { name: "Submit for manager approval" }).click();
  await expect(
    page
      .getByRole("region", { name: "Analyst task detail" })
      .getByText("Manager approval", { exact: true }),
  ).toBeVisible();
});

test("sends the draft to QC as the responsible manager", async ({ page }) => {
  await login(page, "rfa.manager@example.test", "RFA Queue");
  await page.getByRole("button", { name: new RegExp(reference) }).click();
  await page.getByRole("button", { name: "Approve and send to QC" }).click();
  await expect(page.getByText("No tickets in this queue.")).toBeVisible();
});

test("releases the product as QC", async ({ page }) => {
  await login(page, "qc.manager@example.test", "QC Queue");
  await page.getByRole("link", { name: new RegExp(reference) }).click();
  for (const checkbox of await page.getByRole("checkbox").all()) {
    await checkbox.check();
  }
  await page
    .getByRole("combobox", { name: "ACG", exact: true })
    .selectOption({ label: "ACG-EU-CYBER" });
  await page.getByLabel("Approval reason").fill("Approved after controlled QC review.");
  await page.getByRole("button", { name: "Approve and disseminate" }).click();
  await expect(page.getByText("Released to customer")).toBeVisible();
});

test("downloads the released asset bytes as the customer", async ({ page }) => {
  await login(page, "user@example.test", "My Requests");
  await page.goto("/store");
  await page.getByPlaceholder("Search title, summary, tags").fill(assessmentTitle);
  await page.getByRole("button", { name: "Search products" }).click();
  await page.getByText(assessmentTitle, { exact: true }).click();
  await page.getByRole("link", { name: /assessment.txt/ }).click();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download asset" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("assessment.txt");
  const downloadedPath = await download.path();
  if (downloadedPath === null) {
    throw new Error("Playwright did not persist the downloaded asset");
  }
  await expect(readFile(downloadedPath, "utf8")).resolves.toContain("MOCK DATA ONLY");
});
