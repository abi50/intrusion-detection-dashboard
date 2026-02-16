import { useState, useEffect } from "react";

export interface MetricsPoint {
  cpu_percent: number;
  memory_percent: number;
  open_ports: number;
  active_connections: number;
  process_count: number;
  timestamp: string;
}

export function useMetrics(minutes = 30, pollInterval = 10000) {
  const [metrics, setMetrics] = useState<MetricsPoint[]>([]);

  useEffect(() => {
    let active = true;

    const fetchMetrics = async () => {
      try {
        const res = await fetch(`/api/metrics?minutes=${minutes}`);
        if (res.ok && active) setMetrics(await res.json());
      } catch {
        // ignore
      }
    };

    fetchMetrics();
    const id = setInterval(fetchMetrics, pollInterval);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [minutes, pollInterval]);

  return metrics;
}
