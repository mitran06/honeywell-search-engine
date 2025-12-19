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
          minHeight: 0,
        }}
      >
        <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
          {left}
        </div>
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
          minHeight: 0,        // 🔑 critical
          minWidth: 0,         // 🔑 critical
        }}
      >
        {/* IMPORTANT: NO PADDING HERE */}
        <div
          style={{
            flex: 1,
            minHeight: 0,
            minWidth: 0,
            overflow: "hidden",
          }}
        >
          {center}
        </div>
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
          minHeight: 0,
        }}
      >
        <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
          {right}
        </div>
      </aside>
    </div>
  );
}

export default ThreePanelLayout;
