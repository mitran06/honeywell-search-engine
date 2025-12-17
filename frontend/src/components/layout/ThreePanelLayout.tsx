import type { ReactNode } from "react";

interface Props {
  left?: ReactNode;
  center?: ReactNode;
  right?: ReactNode;
  leftWidth?: number;
  rightWidth?: number;
}

export function ThreePanelLayout({
  left,
  center,
  right,
  leftWidth = 280,
  rightWidth = 320,
}: Props) {
  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        gap: 12,
        padding: 12,
        background: "var(--layout-bg)",
        color: "var(--panel-text-primary)",
        overflow: "hidden",
      }}
    >
      {/* LEFT PANEL */}
      <aside
        style={{
          width: leftWidth,
          background: "var(--panel-bg)",
          borderRadius: 16,
          boxShadow: "var(--panel-shadow)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        <div style={{ flex: 1, overflowY: "auto" }}>{left}</div>
      </aside>

      {/* CENTER PANEL */}
      <main
        style={{
          flex: 1,
          background: "var(--panel-bg)",
          borderRadius: 16,
          boxShadow: "var(--panel-shadow)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        <div style={{ flex: 1, padding: 20 }}>{center}</div>
      </main>

      {/* RIGHT PANEL */}
      <aside
        style={{
          width: rightWidth,
          background: "var(--panel-bg)",
          borderRadius: 16,
          boxShadow: "var(--panel-shadow)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        <div style={{ flex: 1, overflowY: "auto" }}>{right}</div>
      </aside>
    </div>
  );
}

export default ThreePanelLayout;
