/**
 * Public runtime configuration. Only NEXT_PUBLIC_* values are readable in the
 * browser — never put TinyFish/OpenAI/OAuth secrets here.
 */
export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/+$/, "");

/**
 * Initial value of the "Sample data" switch. Sample data is a development
 * fixture (see `lib/dev-fixtures`). It defaults to OFF so a production build
 * never presents fixtures as live results; users can still flip it in the UI.
 */
export const DEMO_DEFAULT = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

export const PAGE_SIZE = 6;
