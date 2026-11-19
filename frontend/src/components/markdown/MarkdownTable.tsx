import React from "react";
import { renderInline } from "./inline";

const TABLE_STYLE = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: "0.85rem",
  background: "var(--bg-surface-elevated)",
  borderRadius: "var(--radius-sm)",
  overflow: "hidden",
  border: "1px solid var(--border-color)",
} as const;

export default function MarkdownTable({ headerRow, bodyRows }: { headerRow: string[]; bodyRows: string[][] }) {
  return (
    <div style={{ overflowX: "auto", margin: "12px 0" }}>
      <table className="markdown-table" style={TABLE_STYLE}>
        <thead>
          <tr style={{ background: "var(--bg-surface-hover)", borderBottom: "1px solid var(--border-color)" }}>
            {headerRow.map((col, cIdx) => (
              <th key={cIdx} style={{ padding: "8px 12px", textAlign: "left", fontWeight: 700, color: "var(--text-main)" }}>
                {renderInline(col)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {bodyRows.map((row, rIdx) => (
            <tr
              key={rIdx}
              style={{
                borderBottom: rIdx < bodyRows.length - 1 ? "1px solid var(--border-color)" : "none",
                background: rIdx % 2 === 1 ? "color-mix(in srgb, var(--bg-surface-hover) 40%, transparent)" : "transparent",
              }}
            >
              {row.map((cell, cIdx) => (
                <td key={cIdx} style={{ padding: "8px 12px", verticalAlign: "middle" }}>
                  {renderInline(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
