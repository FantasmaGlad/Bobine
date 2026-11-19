"use client";

export default function TechnicalLogView({ text }: { text: string }) {
  return (
    <div
      className="glass-surface"
      style={{
        padding: "16px",
        fontFamily: "monospace",
        fontSize: "0.75rem",
        color: "var(--text-muted)",
        whiteSpace: "pre-wrap",
        overflowY: "auto",
        maxHeight: "calc(100vh - 260px)",
      }}
    >
      {text}
    </div>
  );
}
