import { useState, useEffect, useCallback } from "react";

export interface Alert {
  id: string;
  rule_id: string;
  severity: string;
  base_score: number;
  message: string;
  source: string;
  payload: Record<string, unknown>;
  acknowledged: boolean;
  created_at: string;
}

export function useAlerts(severity?: string, limit = 50) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (severity) params.set("severity", severity);
      params.set("limit", String(limit));
      const res = await fetch(`/api/alerts?${params}`);
      if (res.ok) setAlerts(await res.json());
    } catch {
      // network error — keep stale data
    } finally {
      setLoading(false);
    }
  }, [severity, limit]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  const acknowledge = useCallback(async (id: string) => {
    const res = await fetch(`/api/alerts/${id}/acknowledge`, { method: "POST" });
    if (res.ok) {
      setAlerts((prev) =>
        prev.map((a) => (a.id === id ? { ...a, acknowledged: true } : a))
      );
    }
  }, []);

  return { alerts, loading, acknowledge, refetch: fetchAlerts };
}
