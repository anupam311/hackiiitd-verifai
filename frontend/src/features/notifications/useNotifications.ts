"use client";

import { useCallback, useMemo } from "react";
import type { AppNotification } from "@/types";
import { useAsync } from "@/hooks/useAsync";
import { useStoredState } from "@/hooks/useStoredState";
import { useDemo } from "@/providers/DemoProvider";
import { getNotifications } from "./api";

/** Notification list with locally stored read state. Live mode shows nothing until the backend provides notifications. */
export function useNotifications() {
  const { demo, ready } = useDemo();
  const state = useAsync((signal) => getNotifications(demo, signal), [demo], ready);
  const [readIds, setReadIds] = useStoredState<string[]>(`verifai.notifications.read.${demo ? "sample" : "live"}`, []);

  const items: AppNotification[] = useMemo(() => (state.data ?? []).map((n) => ({ ...n, read: n.read || readIds.includes(n.id) })), [state.data, readIds]);
  const unread = items.filter((n) => !n.read).length;

  const markRead = useCallback((id: string) => setReadIds((xs) => (xs.includes(id) ? xs : [...xs, id])), [setReadIds]);
  const markAllRead = useCallback(() => setReadIds(items.map((n) => n.id)), [items, setReadIds]);

  return { items, unread, loading: state.loading, error: state.error, reload: state.reload, markRead, markAllRead };
}
