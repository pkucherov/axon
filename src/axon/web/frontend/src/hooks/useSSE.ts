/**
 * Server-Sent Events hook for live graph reload.
 *
 * Opens an EventSource connection to `/api/events` and listens for reindex
 * lifecycle events.  When a `reindex_complete` event fires, the hook fetches
 * fresh graph data *and* analysis data from the API and pushes them into the
 * Zustand stores, causing the UI to re-render with updated data.
 *
 * Reconnects automatically after a 5-second delay on connection errors.
 */

import { useEffect, useRef } from 'react';
import { analysisApi, graphApi } from '@/api/client';
import { useGraphStore } from '@/stores/graphStore';
import { useDataStore } from '@/stores/dataStore';

/**
 * Subscribe to backend SSE events and auto-refresh all data on reindex.
 *
 * Should be called once at the application root (e.g. inside `<App />`).
 */
export function useSSE(): void {
  const sourceRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeRef = useRef(true);
  const setGraphData = useGraphStore((s) => s.setGraphData);
  const setOverview = useGraphStore((s) => s.setOverview);
  const setCommunities = useGraphStore((s) => s.setCommunities);
  const setDeadCode = useDataStore((s) => s.setDeadCode);
  const setHealthScore = useDataStore((s) => s.setHealthScore);

  useEffect(() => {
    function connect(): void {
      const source = new EventSource('/api/events');
      sourceRef.current = source;

      source.addEventListener('reindex_complete', () => {
        // Refresh all data in parallel — same set as useGraph's initial load
        Promise.all([
          graphApi.getGraph(),
          graphApi.getOverview().catch(() => null),
          analysisApi.getCommunities().catch(() => null),
          analysisApi.getDeadCode().catch(() => null),
          analysisApi.getHealth().catch(() => null),
        ])
          .then(([graphData, overview, commResp, deadResp, healthResp]) => {
            if (!activeRef.current) return;
            setGraphData(graphData.nodes, graphData.edges);
            if (overview) setOverview(overview);
            if (commResp) setCommunities(commResp.communities);
            if (deadResp) setDeadCode(deadResp);
            if (healthResp) setHealthScore(healthResp);
          })
          .catch((err: unknown) => {
            console.error('[SSE] Failed to fetch updated data:', err);
          });
      });

      source.addEventListener('reindex_start', () => {
        // Informational -- could trigger a loading spinner in the future.
        console.info('[SSE] Reindex started');
      });

      source.onerror = () => {
        // Close the broken connection and schedule a reconnect.
        source.close();
        sourceRef.current = null;

        reconnectTimerRef.current = setTimeout(() => {
          reconnectTimerRef.current = null;
          connect();
        }, 5_000);
      };
    }

    connect();

    return () => {
      activeRef.current = false;
      sourceRef.current?.close();
      sourceRef.current = null;

      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };
  }, [setGraphData, setOverview, setCommunities, setDeadCode, setHealthScore]);
}
