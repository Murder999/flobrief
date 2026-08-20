"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export interface NotificationFeedItem {
  id: string;
  title: string;
  body: string;
  is_read: boolean;
  created_at: string;
  event_type: string;
  payload?: Record<string, unknown>;
  action_url: string | null;
}

export interface NotificationFeedSource {
  list: (params: { unread_only?: boolean; limit?: number }) => Promise<{
    items: NotificationFeedItem[];
    unread_count: number;
  }>;
  markRead: (id: string) => Promise<unknown>;
  markAllRead: () => Promise<unknown>;
  createRealtimeTicket: () => Promise<{
    ticket: string;
    expires_in_seconds: number;
    websocket_path: string;
  }>;
}

const POLL_INTERVAL_MS = 45_000;
const RECENT_LIMIT = 8;

/** Live notification feed with resilient polling as its delivery safety net. */
export function useNotificationFeed(source: NotificationFeedSource | null) {
  const [unreadCount, setUnreadCount] = useState(0);
  const [recent, setRecent] = useState<NotificationFeedItem[]>([]);
  const sourceRef = useRef(source);
  const refreshPromiseRef = useRef<Promise<void> | null>(null);
  sourceRef.current = source;

  const refresh = useCallback(async () => {
    if (refreshPromiseRef.current) return refreshPromiseRef.current;
    const src = sourceRef.current;
    if (!src) return;
    const pending = (async () => {
      try {
        const data = await src.list({ limit: RECENT_LIMIT });
        setRecent(data.items);
        setUnreadCount(data.unread_count);
      } catch {
        /* WebSocket reconnect/polling retries on the next opportunity. */
      } finally {
        refreshPromiseRef.current = null;
      }
    })();
    refreshPromiseRef.current = pending;
    return pending;
  }, []);

  useEffect(() => {
    if (!source) return;
    void refresh();
    const interval = setInterval(() => void refresh(), POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [source, refresh]);

  useEffect(() => {
    if (!source || typeof window === "undefined") return;

    let stopped = false;
    let connecting = false;
    let reconnectAttempt = 0;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let socket: WebSocket | null = null;

    const scheduleReconnect = () => {
      if (stopped || reconnectTimer || document.visibilityState === "hidden") return;
      const baseDelay = Math.min(30_000, 1_000 * 2 ** reconnectAttempt);
      const jitter = Math.floor(Math.random() * Math.min(1_000, baseDelay / 4));
      reconnectAttempt += 1;
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        void connect();
      }, baseDelay + jitter);
    };

    const connect = async () => {
      if (
        stopped ||
        connecting ||
        socket?.readyState === WebSocket.OPEN ||
        socket?.readyState === WebSocket.CONNECTING
      ) {
        return;
      }
      connecting = true;
      try {
        const ticket = await source.createRealtimeTicket();
        if (stopped) return;
        const configuredBase =
          process.env.NEXT_PUBLIC_WS_URL ||
          process.env.NEXT_PUBLIC_API_URL ||
          window.location.origin;
        const url = new URL(ticket.websocket_path, configuredBase);
        url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
        url.searchParams.set("ticket", ticket.ticket);

        socket = new WebSocket(url.toString());
        socket.onopen = () => {
          reconnectAttempt = 0;
          void refresh();
        };
        socket.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data) as { type?: string };
            if (message.type === "ping") {
              socket?.send(JSON.stringify({ type: "pong" }));
            } else if (message.type === "notifications.changed") {
              void refresh();
            }
          } catch {
            socket?.close(1003, "Invalid message");
          }
        };
        socket.onerror = () => socket?.close();
        socket.onclose = () => {
          socket = null;
          scheduleReconnect();
        };
      } catch {
        scheduleReconnect();
      } finally {
        connecting = false;
      }
    };

    const handleOnline = () => void connect();
    const handleVisibility = () => {
      if (document.visibilityState !== "visible") return;
      void refresh();
      void connect();
    };

    window.addEventListener("online", handleOnline);
    document.addEventListener("visibilitychange", handleVisibility);
    void connect();

    return () => {
      stopped = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      window.removeEventListener("online", handleOnline);
      document.removeEventListener("visibilitychange", handleVisibility);
      if (socket) {
        socket.onclose = null;
        socket.close(1000, "Feed unmounted");
      }
    };
  }, [source, refresh]);

  const markRead = useCallback(async (id: string) => {
    const src = sourceRef.current;
    if (!src) return;
    await src.markRead(id);
    setRecent((items) => items.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
    setUnreadCount((count) => Math.max(0, count - 1));
  }, []);

  const markAllRead = useCallback(async () => {
    const src = sourceRef.current;
    if (!src) return;
    await src.markAllRead();
    setRecent((items) => items.map((n) => ({ ...n, is_read: true })));
    setUnreadCount(0);
  }, []);

  return { unreadCount, recent, refresh, markRead, markAllRead };
}
