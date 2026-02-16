import { useState } from "react";
import AlertsTable from "../components/AlertsTable";
import { useAlerts } from "../hooks/useAlerts";

const severityOptions = ["All", "LOW", "MEDIUM", "HIGH", "CRITICAL"];

export default function Alerts() {
  const [filter, setFilter] = useState<string>("All");
  const severity = filter === "All" ? undefined : filter;
  const { alerts, loading, acknowledge, refetch } = useAlerts(severity, 100);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1.5rem" }}>
        <h2 style={{ margin: 0, fontSize: "1.4rem", fontWeight: 700 }}>Alerts</h2>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          style={{
            padding: "6px 12px",
            borderRadius: 6,
            border: "1px solid #d1d5db",
            fontSize: "0.85rem",
          }}
        >
          {severityOptions.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <button
          onClick={refetch}
          style={{
            padding: "6px 14px",
            borderRadius: 6,
            border: "1px solid #d1d5db",
            background: "#fff",
            cursor: "pointer",
            fontSize: "0.85rem",
          }}
        >
          Refresh
        </button>
      </div>

      <div
        style={{
          background: "#fff",
          borderRadius: 12,
          padding: "1.5rem",
          boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
        }}
      >
        {loading ? (
          <p style={{ color: "#9ca3af" }}>Loading...</p>
        ) : (
          <AlertsTable alerts={alerts} onAcknowledge={acknowledge} />
        )}
      </div>
    </div>
  );
}
