import { expect, test } from "@playwright/test";
import { useSample } from "./helpers";

test.describe("with sample data", () => {
  test.beforeEach(async ({ page }) => useSample(page, true));

  test("discover: sample banner, search, filters, open detail", async ({ page }) => {
    await page.goto("/explore");
    await expect(page.getByRole("heading", { name: "Discover Opportunities" })).toBeVisible();
    await expect(page.getByRole("note").filter({ hasText: "Sample data." })).toBeVisible();
    await expect(page.getByRole("status").filter({ hasText: /Showing/ })).toContainText("of 6 results");

    await page.getByLabel("Search opportunities").fill("scholarship");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(page.getByRole("heading", { level: 3, name: "Undergraduate Scholarship 2027" })).toBeVisible();
    await expect(page.getByRole("heading", { level: 3, name: "Software Engineering Internship 2027" })).toHaveCount(0);

    await page.getByLabel("Search opportunities").fill("");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await page.getByLabel("Category").selectOption("competition");
    await expect(page.getByRole("heading", { level: 3, name: "Build Challenge 2026" })).toBeVisible();
    await page.getByRole("button", { name: /Reset/ }).click();

    await page.getByRole("link", { name: "Software Engineering Internship 2027", exact: true }).first().click();
    await expect(page.getByRole("heading", { level: 1, name: "Software Engineering Internship 2027" })).toBeVisible();
  });

  test("detail: conflicts stay visible and evidence is inspectable", async ({ page }) => {
    await page.goto("/opportunities/demo-helio-swe");
    await expect(page.getByRole("alert").filter({ hasText: "Conflicting information found" })).toContainText("Stipend");
    // Regression: a confirmed deadline that sources merely format differently is not a conflict.
    await expect(page.getByRole("alert").filter({ hasText: "Conflicting information found" })).not.toContainText("Deadline");
    await page.getByRole("tab", { name: "Verification Report" }).click();
    await expect(page.getByRole("heading", { name: "Conflicts detected" })).toBeVisible();
    await page.getByRole("button", { name: /Evidence/ }).nth(4).click();
    await expect(page.getByText("Monthly stipend of ₹1,20,000")).toBeVisible();
    await page.getByRole("tab", { name: /Sources/ }).click();
    await expect(page.getByRole("table", { name: /Claims compared across sources/ })).toBeVisible();
    await expect(page.getByText("Timed out", { exact: true })).toBeVisible();
  });

  test("missing deadline is shown as unknown, never invented", async ({ page }) => {
    await page.goto("/opportunities/demo-aldrin-research");
    await expect(page.getByText("Deadline unknown").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Partially verified" }).or(page.getByRole("heading", { name: "Verification incomplete" }))).toHaveCount(0); // overview shows badge, not banner
    await page.getByRole("tab", { name: "Verification Report" }).click();
    await expect(page.getByRole("heading", { name: "Partially verified" })).toBeVisible();
    await expect(page.getByText("Important claims were not checked").or(page.getByText("When is the application deadline?"))).toBeVisible();
  });

  test("save, view in saved list, remove", async ({ page }) => {
    await page.goto("/explore");
    await page.getByRole("button", { name: "Save: Software Engineering Internship 2027" }).click();
    await expect(page.getByRole("button", { name: "Remove from saved: Software Engineering Internship 2027" })).toBeVisible();
    await page.getByRole("link", { name: "Saved Opportunities" }).click();
    await expect(page.getByRole("heading", { level: 2, name: "Software Engineering Internship 2027" })).toBeVisible();
    await page.getByRole("button", { name: "Remove Software Engineering Internship 2027 from saved" }).click();
    await expect(page.getByRole("heading", { level: 2, name: "Software Engineering Internship 2027" })).toHaveCount(0);
  });

  test("recheck in sample mode is honest about not running", async ({ page }) => {
    await page.goto("/explore");
    await page.getByRole("button", { name: "Recheck" }).first().click();
    await expect(page.getByText("Sample mode — no live recheck was run")).toBeVisible();
    await expect(page).toHaveURL(/\/recheck\?opp=/);
    await expect(page.getByText("Sample run log").first()).toBeVisible();
  });

  test("history shows confirmed changes and new conflicts", async ({ page }) => {
    await page.goto("/history?opp=demo-helio-swe");
    await expect(page.getByText("Confirmed changes").first()).toBeVisible();
    await expect(page.getByText("New conflict").first()).toBeVisible();
  });

  test("profile validation blocks bad graduation year", async ({ page }) => {
    await page.goto("/profile");
    await page.getByLabel("Expected graduation year").fill("1850");
    await page.getByRole("button", { name: "Save profile" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "between 1990 and 2100" })).toBeVisible();
    await page.getByLabel("Expected graduation year").fill("2027");
    await page.getByRole("button", { name: "Save profile" }).click();
    await expect(page.getByText("Profile saved")).toBeVisible();
  });

  test("checklist tick persists across reload", async ({ page }) => {
    await page.goto("/checklist/demo-helio-swe");
    const box = page.getByLabel(/Complete the online application form/);
    await box.check();
    await page.reload();
    await expect(page.getByLabel(/Complete the online application form/)).toBeChecked();
    await expect(page.getByText(/does not submit applications/)).toBeVisible();
  });

  test("passport: no profile by default, print and export available", async ({ page }) => {
    await page.goto("/passport/demo-helio-swe");
    await expect(page.getByRole("heading", { name: "Verification Passport" })).toBeVisible();
    await expect(page.getByText("Eligibility fit (included by the applicant)")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Print / Save as PDF" })).toBeEnabled();
    const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Download JSON" }).click()]);
    expect(download.suggestedFilename()).toBe("verifai-passport-demo-helio-swe.json");
    await page.getByLabel(/Include my eligibility match/).check();
    await expect(page.getByText("Eligibility fit (included by the applicant)")).toBeVisible();
  });

  test("compare opportunities workspace", async ({ page }) => {
    await page.goto("/explore");
    await page.getByRole("checkbox", { name: "Compare" }).nth(0).check();
    await page.getByRole("checkbox", { name: "Compare" }).nth(1).check();
    await page.getByRole("link", { name: "Compare", exact: true }).click();
    await expect(page.getByRole("table", { name: /compared side by side/ })).toBeVisible();
    await expect(page.getByRole("rowheader", { name: "Source evidence quality" })).toBeVisible();
  });

  test("notifications are labelled as sample", async ({ page }) => {
    await page.goto("/notifications");
    await expect(page.getByText("No monitoring service is running")).toBeVisible();
  });
});

test.describe("live mode without a reachable backend", () => {
  test.beforeEach(async ({ page }) => useSample(page, false));

  test("discover shows an honest error, not sample results", async ({ page }) => {
    await page.goto("/explore");
    await expect(page.getByRole("alert").filter({ hasText: "Could not reach the VERIFAI API" })).toBeVisible();
    await expect(page.getByText("Helio Systems")).toHaveCount(0);
    await expect(page.getByRole("note").filter({ hasText: "Sample data." })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  });

  test("login explains unavailability and disables providers", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("button", { name: "Continue with Google" })).toBeDisabled();
    await expect(page.getByText("API unreachable").first()).toBeVisible();
  });

  test("notifications do not pretend to monitor", async ({ page }) => {
    await page.goto("/notifications");
    await expect(page.getByRole("alert").or(page.getByText("aren’t available yet"))).toBeVisible();
  });
});

test.describe("accessibility basics", () => {
  test("landmarks, skip link, tab keyboard navigation", async ({ page }) => {
    await useSample(page, true);
    await page.goto("/opportunities/demo-helio-swe");
    await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
    await expect(page.getByRole("main")).toBeVisible();
    await page.getByRole("tab", { name: "Overview" }).focus();
    await page.keyboard.press("ArrowRight");
    await expect(page.getByRole("tab", { name: "Verification Report" })).toHaveAttribute("aria-selected", "true");
    await page.keyboard.press("End");
    await expect(page.getByRole("tab", { name: "Similar Opportunities" })).toHaveAttribute("aria-selected", "true");
  });
});
