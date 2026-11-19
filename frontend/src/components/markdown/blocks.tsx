import React from "react";
import { renderInline } from "./inline";
import MarkdownTable from "./MarkdownTable";

export type Parsed = { node: React.ReactNode; next: number };
type BlockRule = (lines: string[], i: number, trimmed: string) => Parsed | null;

const PRE_STYLE = {
  background: "var(--bg-surface-elevated)",
  padding: "10px 12px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border-color)",
  overflowX: "auto",
  fontSize: "0.82rem",
  margin: "8px 0",
  color: "var(--text-muted)",
} as const;

const HEADINGS = [
  { pattern: /^#\s+(.+)$/, Tag: "h1", style: { fontSize: "1.35rem", fontWeight: 800, margin: "14px 0 8px", color: "var(--text-main)" } },
  { pattern: /^##\s+(.+)$/, Tag: "h2", style: { fontSize: "1.15rem", fontWeight: 700, margin: "14px 0 6px", color: "var(--text-main)" } },
  { pattern: /^###\s+(.+)$/, Tag: "h3", style: { fontSize: "1rem", fontWeight: 700, margin: "10px 0 4px", color: "var(--text-main)" } },
] as const;

const rule: BlockRule = (_lines, i, trimmed) => {
  if (!/^---$|^___$|^\*\*\*$/.test(trimmed)) return null;
  return { node: <hr key={`hr-${i}`} style={{ border: "none", borderTop: "1px solid var(--border-color)", margin: "16px 0" }} />, next: i + 1 };
};

const heading: BlockRule = (_lines, i, trimmed) => {
  for (const { pattern, Tag, style } of HEADINGS) {
    const match = trimmed.match(pattern);
    if (match) return { node: <Tag key={`${Tag}-${i}`} style={style}>{renderInline(match[1])}</Tag>, next: i + 1 };
  }
  return null;
};

const fence: BlockRule = (lines, i, trimmed) => {
  if (!trimmed.startsWith("```")) return null;
  const codeLines: string[] = [];
  let j = i + 1;
  while (j < lines.length && !lines[j].trim().startsWith("```")) {
    codeLines.push(lines[j]);
    j++;
  }
  j++;
  return { node: <pre key={`code-block-${j}`} style={PRE_STYLE}><code>{codeLines.join("\n")}</code></pre>, next: j };
};

const cells = (line: string) => line.trim().slice(1, -1).split("|").map((c) => c.trim());

const table: BlockRule = (lines, i, trimmed) => {
  if (!(trimmed.startsWith("|") && trimmed.endsWith("|") && i + 1 < lines.length && lines[i + 1].includes("---"))) return null;
  const headerRow = cells(trimmed);
  let j = i + 2;
  const bodyRows: string[][] = [];
  while (j < lines.length && lines[j].trim().startsWith("|") && lines[j].trim().endsWith("|")) {
    bodyRows.push(cells(lines[j]));
    j++;
  }
  return { node: <MarkdownTable key={`table-wrap-${j}`} headerRow={headerRow} bodyRows={bodyRows} />, next: j };
};

const isItem = (line: string) => line.trim().startsWith("- ") || line.trim().startsWith("* ");

const list: BlockRule = (lines, i, trimmed) => {
  if (!isItem(trimmed)) return null;
  const listItems: string[] = [];
  let j = i;
  while (j < lines.length && isItem(lines[j])) {
    listItems.push(lines[j].trim().slice(2));
    j++;
  }
  return {
    node: (
      <ul key={`ul-${j}`} style={{ margin: "8px 0", paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "4px" }}>
        {listItems.map((it, idx) => (
          <li key={idx} style={{ color: "var(--text-main)", fontSize: "0.88rem", lineHeight: 1.5 }}>
            {renderInline(it)}
          </li>
        ))}
      </ul>
    ),
    next: j,
  };
};

const paragraph: BlockRule = (_lines, i, trimmed) => ({
  node: (
    <p key={`p-${i}`} style={{ margin: "6px 0", lineHeight: 1.6, fontSize: "0.88rem", color: "var(--text-main)" }}>
      {renderInline(trimmed)}
    </p>
  ),
  next: i + 1,
});

const BLOCKS = [rule, heading, fence, table, list, paragraph];

export function parseBlock(lines: string[], i: number, trimmed: string): Parsed {
  for (const block of BLOCKS) {
    const parsed = block(lines, i, trimmed);
    if (parsed) return parsed;
  }
  return paragraph(lines, i, trimmed) as Parsed;
}
