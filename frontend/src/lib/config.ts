/**
 * Public runtime configuration. Only NEXT_PUBLIC_* values are readable in the
 * browser — never put TinyFish/OpenAI/OAuth secrets here.
 */
// Unset: development calls http://localhost:8000 directly; a production build calls its own origin, where
// next.config.mjs proxies /api, /auth and /health to BACKEND_URL (first-party session cookie).
const DEFAULT_API = process.env.NODE_ENV === "production" ? "" : "http://localhost:8000";
export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API).replace(/\/+$/, "");

/**
 * Initial value of the "Sample data" switch. Sample data is a development
 * fixture (see `lib/dev-fixtures`). It defaults to OFF so a production build
 * never presents fixtures as live results; users can still flip it in the UI.
 */
export const DEMO_DEFAULT = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

export const PAGE_SIZE = 6;
