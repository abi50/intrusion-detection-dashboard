import { useState, useEffect } from "react";

export interface RiskPoint {
  score: number;
  timestamp: string;
}

export function useRisk(limit = 360, pollInterval = 10000) {
  const [risk, setRisk] = useState<RiskPoint[]>([]);

  useEffect(() => {
    let active = true;

    const fetchRisk = async () => {
      try {
        const res = await fetch(`/api/risk?limit=${limit}`);
        if (res.ok && active) setRisk(await res.json());
      } catch {
        // ignore
      }
    };

    fetchRisk();
    const id = setInterval(fetchRisk, pollInterval);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [limit, pollInterval]);

  return risk;
}
