import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/", label: "Dashboard" },
  { to: "/alerts", label: "Alerts" },
  { to: "/settings", label: "Settings" },
];

export default function Layout() {
  return (
    <div style={{ display: "flex", minHeight: "100vh", fontFamily: "system-ui, sans-serif" }}>
      {/* Sidebar */}
      <nav
        style={{
          width: 220,
          background: "#111827",
          color: "#f9fafb",
          padding: "1.5rem 0",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div style={{ padding: "0 1.25rem", marginBottom: "2rem" }}>
          <h1 style={{ fontSize: "1.1rem", fontWeight: 700, margin: 0, letterSpacing: "-0.02em" }}>
            IDS Dashboard
          </h1>
          <span style={{ fontSize: "0.75rem", color: "#9ca3af" }}>Intrusion Detection</span>
        </div>

        {navItems.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            style={({ isActive }) => ({
              display: "block",
              padding: "0.6rem 1.25rem",
              color: isActive ? "#fff" : "#9ca3af",
              background: isActive ? "#1f2937" : "transparent",
              textDecoration: "none",
              fontSize: "0.9rem",
              borderLeft: isActive ? "3px solid #3b82f6" : "3px solid transparent",
            })}
          >
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Main content */}
      <main style={{ flex: 1, background: "#f9fafb", padding: "1.5rem 2rem", overflowY: "auto" }}>
        <Outlet />
      </main>
    </div>
  );
}
