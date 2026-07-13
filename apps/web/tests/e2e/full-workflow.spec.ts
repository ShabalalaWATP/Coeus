import { expect, test } from "@playwright/test";

import { createFlowState, installApiMocks } from "./full-workflow-mocks";

test("drives request, JIOC routing, analyst, manager approval and QC release", async ({ page }) => {
  await installApiMocks(page, createFlowState());

  await page.goto("/app/requests");
  await page.getByRole("button", { name: "Open new request" }).click();
  await page.getByLabel("Message").fill("Need a routine assessment near North Atlantic lanes.");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("TCK-E2E")).toBeVisible();
  await page.getByText("Edit details manually").click();
  await page.getByRole("button", { name: "Submit" }).click();
  await expect(page.getByRole("dialog", { name: "Request journey" })).toBeVisible();
  await page.getByLabel("Close journey").click();

  await page.goto("/jioc/queue");
  await expect(page.getByRole("heading", { name: "JIOC Queue" })).toBeVisible();
  await page.getByRole("button", { name: "Run capability checks" }).click();
  await expect(page.getByText("Recommended route: RFA")).toBeVisible();
  await page.getByRole("button", { name: "Approve route" }).click();
  await expect(page.getByText("No tickets in this queue.")).toBeVisible();

  await page.goto("/rfa/queue");
  await expect(page.getByRole("heading", { name: "RFA Queue" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Assign analysts" })).toBeVisible();
  await page.getByRole("checkbox", { name: "Analyst Operator" }).check();
  await page.getByRole("button", { name: "Assign analysts" }).click();

  await page.goto("/analyst/workbench");
  await expect(page.getByRole("heading", { name: "Analyst Workbench" })).toBeVisible();
  await page.getByLabel("Assess vessel activity").click();
  await expect(page.getByLabel("Assess vessel activity")).toBeChecked();
  await page.getByLabel("Title").fill("North Atlantic Assessment");
  await page.getByLabel("Summary").fill("Synthetic assessment summary.");
  await page.getByLabel("Content").fill("Synthetic assessment content for QC review.");
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("v1: North Atlantic Assessment")).toBeVisible();
  await page.getByRole("button", { name: "Submit for manager approval" }).click();
  await expect(
    page.getByLabel("Analyst task detail").getByText("Manager approval", { exact: true }),
  ).toBeVisible();

  await page.goto("/rfa/queue");
  await page.getByRole("button", { name: "Approve and send to QC" }).click();
  await expect(page.getByText("No tickets in this queue.")).toBeVisible();

  await page.goto("/qc/queue");
  await expect(page.getByRole("heading", { name: "QC Queue" })).toBeVisible();
  await page.getByRole("button", { name: /TCK-E2E/ }).click();
  await page.getByRole("checkbox", { name: "source checked" }).check();
  await page.getByRole("checkbox", { name: "classification checked" }).check();
  await page.getByLabel("ACG").selectOption("acg-alpha");
  await page.getByLabel("Approval reason").fill("Approved after QC review.");
  await page.getByRole("button", { name: "Approve and disseminate" }).click();
  await expect(page.getByText("Released to customer")).toBeVisible();
});
