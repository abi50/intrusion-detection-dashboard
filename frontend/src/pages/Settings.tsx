import { useState, useEffect } from "react";

interface Rule {
  id: string;
  description: string;
  source: string;
  severity: string;
  weight: number;
  condition: {
    field: string;
    operator: string;
    value: unknown;
    sustained_seconds?: number;
    window_seconds?: number;
  };
}

const severityColors: Record<string, string> = {
  LOW: "#3b82f6",
  MEDIUM: "#eab308",
  HIGH: "#f97316",
  CRITICAL: "#ef4444",
};

export default function Settings() {
  const [rules, setRules] = useState<Rule[]>([]);

  useEffect(() => {
    fetch("/api/rules")
      .then((r) => r.json())
      .then(setRules)
      .catch(() => {});
  }, []);

  return (
    <div>
      <h2 style={{ margin: "0 0 1.5rem", fontSize: "1.4rem", fontWeight: 700 }}>Detection Rules</h2>

      <div
        style={{
          background: "#fff",
          borderRadius: 12,
          padding: "1.5rem",
          boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
        }}
      >
        {rules.length === 0 ? (
          <p style={{ color: "#9ca3af", fontStyle: "italic" }}>No rules loaded</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
            <thead>
              <tr style={{ borderBottom: "2px solid #e5e7eb", textAlign: "left" }}>
                <th style={thStyle}>ID</th>
                <th style={thStyle}>Description</th>
                <th style={thStyle}>Source</th>
                <th style={thStyle}>Severity</th>
                <th style={thStyle}>Weight</th>
                <th style={thStyle}>Condition</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                  <td style={tdStyle}>
                    <code style={{ fontSize: "0.8rem" }}>{r.id}</code>
                  </td>
                  <td style={tdStyle}>{r.description}</td>
                  <td style={tdStyle}>{r.source}</td>
                  <td style={tdStyle}>
                    <span
                      style={{
                        display: "inline-block",
                        padding: "2px 8px",
                        borderRadius: 9999,
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        color: "#fff",
                        background: severityColors[r.severity] || "#6b7280",
                      }}
                    >
                      {r.severity}
                    </span>
                  </td>
                  <td style={tdStyle}>{r.weight}</td>
                  <td style={tdStyle}>
                    <code style={{ fontSize: "0.8rem", background: "#f3f4f6", padding: "2px 6px", borderRadius: 4 }}>
                      {r.condition.field} {r.condition.operator} {JSON.stringify(r.condition.value)}
                    </code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

const thStyle: React.CSSProperties = { padding: "8px 12px", fontWeight: 600, color: "#374151" };
const tdStyle: React.CSSProperties = { padding: "8px 12px" };
