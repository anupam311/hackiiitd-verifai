import type { AppNotification } from "@/types";
import { api } from "@/lib/api-client";
import { DEMO_NOTIFICATIONS } from "@/lib/dev-fixtures/demo-data";

/** `GET /api/v1/notifications` is not in docs/api.md yet; a 404 surfaces as "not available". */
export async function getNotifications(demo: boolean, signal?: AbortSignal): Promise<AppNotification[]> {
  if (demo) return DEMO_NOTIFICATIONS;
  const raw = await api.get<{ items?: AppNotification[] }>("/api/v1/notifications", undefined, signal);
  return raw.items ?? [];
}
