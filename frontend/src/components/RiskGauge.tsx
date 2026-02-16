interface Props {
  score: number;
}

function riskColor(score: number): string {
  if (score < 30) return "#22c55e";
  if (score < 60) return "#eab308";
  return "#ef4444";
}

function riskLabel(score: number): string {
  if (score < 30) return "Low";
  if (score < 60) return "Medium";
  return "High";
}

export default function RiskGauge({ score }: Props) {
  const color = riskColor(score);
  return (
    <div
      style={{
        background: "#fff",
        borderRadius: 12,
        padding: "1.5rem",
        boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: "0.85rem", color: "#6b7280", marginBottom: 8 }}>Risk Score</div>
      <div style={{ fontSize: "3rem", fontWeight: 700, color, lineHeight: 1 }}>
        {Math.round(score)}
      </div>
      <div
        style={{
          marginTop: 8,
          display: "inline-block",
          padding: "2px 12px",
          borderRadius: 9999,
          fontSize: "0.8rem",
          fontWeight: 600,
          color: "#fff",
          background: color,
        }}
      >
        {riskLabel(score)}
      </div>
    </div>
  );
}
