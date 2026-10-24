import type { Page } from "@playwright/test";

/** Turn the sample-data switch on/off before the app loads. */
export async function useSample(page: Page, on: boolean) {
  await page.addInitScript((v) => {
    window.localStorage.setItem("verifai.sample-data", v ? "on" : "off");
  }, on);
}
