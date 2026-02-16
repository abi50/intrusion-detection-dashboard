import { useState, useEffect } from "react";

export interface SystemStatus {
  status: string;
  event_bus_running: boolean;
  subscribers: number;
  pending_events: number;
  collectors: number;
}

export function useStatus(pollInterval = 5000) {
  const [status, setStatus] = useState<SystemStatus | null>(null);

  useEffect(() => {
    let active = true;

    const fetchStatus = async () => {
      try {
        const res = await fetch("/api/status");
        if (res.ok && active) setStatus(await res.json());
      } catch {
        // ignore
      }
    };

    fetchStatus();
    const id = setInterval(fetchStatus, pollInterval);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [pollInterval]);

  return status;
}
