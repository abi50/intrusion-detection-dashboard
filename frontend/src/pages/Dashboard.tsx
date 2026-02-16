import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import RiskGauge from "../components/RiskGauge";
import AlertsTable from "../components/AlertsTable";
import { useWebSocket } from "../hooks/useWebSocket";
import { useAlerts, type Alert } from "../hooks/useAlerts";
import { useMetrics } from "../hooks/useMetrics";
import { useRisk } from "../hooks/useRisk";
import { useStatus } from "../hooks/useStatus";

export default function Dashboard() {
  const { lastAlert, riskScore, connected } = useWebSocket();
  const { alerts, refetch } = useAlerts(undefined, 10);
  const metrics = useMetrics();
  const risk = useRisk(120);
  const status = useStatus();

  // Merge real-time alerts into the list
  const [realtimeAlerts, setRealtimeAlerts] = useState<Alert[]>([]);
  useEffect(() => {
    if (lastAlert) {
      setRealtimeAlerts((prev) => {
        const merged = [lastAlert, ...prev.filter((a) => a.id !== lastAlert.id)];
        return merged.slice(0, 10);
      });
    }
  }, [lastAlert]);

  const displayAlerts = realtimeAlerts.length > 0 ? realtimeAlerts : alerts;
  const currentRisk = riskScore || (risk.length > 0 ? risk[0].score : 0);

  // Format chart data (reverse so oldest is first)
  const riskData = [...risk].reverse().map((r) => ({
    time: new Date(r.timestamp).toLocaleTimeString(),
    score: Math.round(r.score * 10) / 10,
  }));

  const metricsData = [...metrics].reverse().map((m) => ({
    time: new Date(m.timestamp).toLocaleTimeString(),
    cpu: Math.round(m.cpu_percent * 10) / 10,
    memory: Math.round(m.memory_percent * 10) / 10,
  }));

  return (
    <div>
      <h2 style={{ margin: "0 0 1.5rem", fontSize: "1.4rem", fontWeight: 700 }}>Dashboard</h2>

      {/* Top row: Risk + Status */}
      <div style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: "1rem", marginBottom: "1.5rem" }}>
        <RiskGauge score={currentRisk} />

        <div style={cardStyle}>
          <div style={{ fontSize: "0.85rem", color: "#6b7280", marginBottom: 12 }}>System Status</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "1rem" }}>
            <Stat label="Status" value={status?.status || "..."} />
            <Stat label="Collectors" value={status?.collectors ?? "..."} />
            <Stat label="Event Bus" value={status?.event_bus_running ? "Running" : "Stopped"} />
            <Stat
              label="WebSocket"
              value={connected ? "Connected" : "Disconnected"}
              color={connected ? "#22c55e" : "#ef4444"}
            />
          </div>
        </div>
      </div>

      {/* Charts row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1.5rem" }}>
        <div style={cardStyle}>
          <div style={{ fontSize: "0.85rem", color: "#6b7280", marginBottom: 12 }}>Risk Score Trend</div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={riskData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line type="monotone" dataKey="score" stroke="#ef4444" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div style={cardStyle}>
          <div style={{ fontSize: "0.85rem", color: "#6b7280", marginBottom: 12 }}>CPU & Memory</div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={metricsData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
              <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
              <Tooltip />
              <Area type="monotone" dataKey="cpu" stroke="#3b82f6" fill="#93c5fd" fillOpacity={0.3} />
              <Area type="monotone" dataKey="memory" stroke="#8b5cf6" fill="#c4b5fd" fillOpacity={0.3} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Recent alerts */}
      <div style={cardStyle}>
        <div style={{ fontSize: "0.85rem", color: "#6b7280", marginBottom: 12 }}>Recent Alerts</div>
        <AlertsTable alerts={displayAlerts} compact />
      </div>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div>
      <div style={{ fontSize: "0.75rem", color: "#9ca3af" }}>{label}</div>
      <div style={{ fontSize: "1.1rem", fontWeight: 600, color: color || "#111827" }}>{String(value)}</div>
    </div>
  );
}

const cardStyle: React.CSSProperties = {
  background: "#fff",
  borderRadius: 12,
  padding: "1.5rem",
  boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
};
