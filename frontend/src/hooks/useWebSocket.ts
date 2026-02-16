import { useEffect, useRef, useState, useCallback } from "react";

export interface WsAlert {
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

interface WsMessage {
  type: string;
  alert: WsAlert;
  risk_score: number;
}

export function useWebSocket() {
  const [lastAlert, setLastAlert] = useState<WsAlert | null>(null);
  const [riskScore, setRiskScore] = useState<number>(0);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/events`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);

    ws.onmessage = (evt) => {
      try {
        const data: WsMessage = JSON.parse(evt.data);
        if (data.type === "alert") {
          setLastAlert(data.alert);
          setRiskScore(data.risk_score);
        }
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      setConnected(false);
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { lastAlert, riskScore, connected };
}
