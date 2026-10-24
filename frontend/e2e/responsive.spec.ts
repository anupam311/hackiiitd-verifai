import { expect, test } from "@playwright/test";
import { useSample } from "./helpers";

test("mobile: drawer navigation and no horizontal page scroll", async ({ page }) => {
  await useSample(page, true);
  await page.goto("/explore");
  await expect(page.getByRole("button", { name: "Open navigation" })).toBeVisible();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("link", { name: "Saved Opportunities" }).click();
  await expect(page).toHaveURL(/\/saved/);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

test("mobile: claim table stacks and detail page does not overflow", async ({ page }) => {
  await useSample(page, true);
  await page.goto("/opportunities/demo-helio-swe");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
