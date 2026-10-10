/**
 * src/hooks/useRealtimeEvents.ts
 * Real-time event subscription for flags, cases, integrity alerts, and metrics.
 * Connects via WebSocket (/api/v1/events/ws?token=...), reconnects on failure,
 * and invalidates relevant TanStack Query caches automatically.
 */

import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { getToken } from '@/api/client';

export function useRealtimeEvents() {
  const queryClient = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);

  useEffect(() => {
    let isCancelled = false;

    function connect() {
      const token = getToken();
      if (!token) {
        // Retry later when token is available
        reconnectTimerRef.current = window.setTimeout(connect, 3000);
        return;
      }

      // Determine WS protocol and URL
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/api/v1/events/ws?token=${encodeURIComponent(token)}`;

      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          // Connected successfully
        };

        ws.onmessage = (e) => {
          try {
            const data = JSON.parse(e.data);
            const eventType = data.event_type || data.type;

            if (eventType === 'PING') return;

            // Invalidate relevant query keys
            if (eventType === 'FLAG_CREATED' || eventType === 'FLAG_RESOLVED') {
              queryClient.invalidateQueries({ queryKey: ['flags'] });
              queryClient.invalidateQueries({ queryKey: ['centres'] });
            } else if (eventType === 'INTEGRITY_ALERT' || eventType === 'CAMERA_REBASELINED') {
              queryClient.invalidateQueries({ queryKey: ['cameras'] });
              queryClient.invalidateQueries({ queryKey: ['centres'] });
            } else if (eventType === 'CASE_CREATED' || eventType === 'CASE_UPDATED') {
              queryClient.invalidateQueries({ queryKey: ['cases'] });
            } else if (eventType === 'OBSERVATION_INGESTED' || eventType === 'RECONCILIATION_COMPLETED') {
              queryClient.invalidateQueries({ queryKey: ['sessions'] });
              queryClient.invalidateQueries({ queryKey: ['centres'] });
              queryClient.invalidateQueries({ queryKey: ['flags'] });
            } else {
              // General event: invalidate overview and flags
              queryClient.invalidateQueries({ queryKey: ['flags'] });
              queryClient.invalidateQueries({ queryKey: ['centres'] });
            }
          } catch {
            // Ignore non-json frames
          }
        };

        ws.onclose = () => {
          if (!isCancelled) {
            reconnectTimerRef.current = window.setTimeout(connect, 5000);
          }
        };

        ws.onerror = () => {
          try {
            ws.close();
          } catch {
            // ignore
          }
        };
      } catch {
        if (!isCancelled) {
          reconnectTimerRef.current = window.setTimeout(connect, 5000);
        }
      }
    }

    connect();

    return () => {
      isCancelled = true;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch {
          // ignore
        }
      }
    };
  }, [queryClient]);
}
