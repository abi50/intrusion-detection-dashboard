import type { Alert } from "../hooks/useAlerts";

const severityColors: Record<string, string> = {
  LOW: "#3b82f6",
  MEDIUM: "#eab308",
  HIGH: "#f97316",
  CRITICAL: "#ef4444",
};

interface Props {
  alerts: Alert[];
  onAcknowledge?: (id: string) => void;
  compact?: boolean;
}

export default function AlertsTable({ alerts, onAcknowledge, compact }: Props) {
  if (alerts.length === 0) {
    return <p style={{ color: "#9ca3af", fontStyle: "italic" }}>No alerts</p>;
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: "0.85rem",
        }}
      >
        <thead>
          <tr style={{ borderBottom: "2px solid #e5e7eb", textAlign: "left" }}>
            <th style={thStyle}>Severity</th>
            <th style={thStyle}>Rule</th>
            <th style={thStyle}>Message</th>
            {!compact && <th style={thStyle}>Source</th>}
            <th style={thStyle}>Score</th>
            <th style={thStyle}>Time</th>
            {onAcknowledge && <th style={thStyle}>Action</th>}
          </tr>
        </thead>
        <tbody>
          {alerts.map((a) => (
            <tr
              key={a.id}
              style={{
                borderBottom: "1px solid #f3f4f6",
                opacity: a.acknowledged ? 0.5 : 1,
              }}
            >
              <td style={tdStyle}>
                <span
                  style={{
                    display: "inline-block",
                    padding: "2px 8px",
                    borderRadius: 9999,
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    color: "#fff",
                    background: severityColors[a.severity] || "#6b7280",
                  }}
                >
                  {a.severity}
                </span>
              </td>
              <td style={tdStyle}>{a.rule_id}</td>
              <td style={tdStyle}>{a.message}</td>
              {!compact && <td style={tdStyle}>{a.source}</td>}
              <td style={tdStyle}>{a.base_score}</td>
              <td style={tdStyle}>{formatTime(a.created_at)}</td>
              {onAcknowledge && (
                <td style={tdStyle}>
                  {!a.acknowledged && (
                    <button
                      onClick={() => onAcknowledge(a.id)}
                      style={{
                        padding: "3px 10px",
                        fontSize: "0.75rem",
                        border: "1px solid #d1d5db",
                        borderRadius: 6,
                        background: "#fff",
                        cursor: "pointer",
                      }}
                    >
                      Ack
                    </button>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const thStyle: React.CSSProperties = { padding: "8px 12px", fontWeight: 600, color: "#374151" };
const tdStyle: React.CSSProperties = { padding: "8px 12px" };

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString();
  } catch {
    return iso;
  }
}
