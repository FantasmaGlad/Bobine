"use client";

import React from "react";

interface MarkdownViewProps {
  content: string;
  className?: string;
}

/**
 * Composant de rendu Markdown natif, sécurisé et sans dépendance externe lourde.
 * Optimisé pour afficher fidèlement les notes de versions GitHub :
 * - Titres h1, h2, h3
 * - Tableaux Markdown avec en-têtes et bordures
 * - Badges shields.io et images
 * - Liens cliquables avec target="_blank"
 * - Listes à puces
 * - Blocs de code et code inline
 * - Gras, italique et séparateurs horizontaux
 */
export default function MarkdownView({ content, className = "" }: MarkdownViewProps) {
  if (!content) return null;

  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const elements: React.ReactNode[] = [];
  let i = 0;

  const renderInline = (text: string): React.ReactNode[] => {
    const nodes: React.ReactNode[] = [];
    let remaining = text;
    let keyIdx = 0;

    while (remaining.length > 0) {
      // 1. Image markdown : ![alt](url)
      const imgMatch = remaining.match(/^!\[(.*?)\]\((.*?)\)/);
      if (imgMatch) {
        const alt = imgMatch[1];
        const src = imgMatch[2];
        nodes.push(
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={`img-${keyIdx++}`}
            src={src}
            alt={alt}
            style={{ display: "inline-block", verticalAlign: "middle", maxWidth: "100%", margin: "2px 4px" }}
            loading="lazy"
          />
        );
        remaining = remaining.slice(imgMatch[0].length);
        continue;
      }

      // 2. Balise HTML <img> simple : <img ... src="..." ... />
      const htmlImgMatch = remaining.match(/^<img\s+([^>]*?)src=["'](.*?)["']([^>]*?)\/?>/i);
      if (htmlImgMatch) {
        const src = htmlImgMatch[2];
        nodes.push(
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={`himg-${keyIdx++}`}
            src={src}
            alt=""
            style={{ display: "inline-block", verticalAlign: "middle", maxWidth: "100%", margin: "2px 4px" }}
            loading="lazy"
          />
        );
        remaining = remaining.slice(htmlImgMatch[0].length);
        continue;
      }

      // 3. Lien markdown : [texte](url)
      const linkMatch = remaining.match(/^\[(.*?)\]\((.*?)\)/);
      if (linkMatch) {
        const linkText = linkMatch[1];
        const linkUrl = linkMatch[2];
        nodes.push(
          <a
            key={`link-${keyIdx++}`}
            href={linkUrl}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "var(--accent-primary)", fontWeight: 600, textDecoration: "underline" }}
          >
            {renderInline(linkText)}
          </a>
        );
        remaining = remaining.slice(linkMatch[0].length);
        continue;
      }

      // 4. Code inline : `code`
      const codeMatch = remaining.match(/^`([^`]+)`/);
      if (codeMatch) {
        nodes.push(
          <code
            key={`code-${keyIdx++}`}
            style={{
              background: "var(--bg-surface-elevated)",
              padding: "2px 6px",
              borderRadius: "4px",
              fontSize: "0.85em",
              fontFamily: "monospace",
              color: "var(--accent-primary)",
              border: "1px solid var(--border-color)",
            }}
          >
            {codeMatch[1]}
          </code>
        );
        remaining = remaining.slice(codeMatch[0].length);
        continue;
      }

      // 5. Gras : **texte**
      const boldMatch = remaining.match(/^\*\*([^*]+)\*\*/);
      if (boldMatch) {
        nodes.push(<strong key={`bold-${keyIdx++}`}>{renderInline(boldMatch[1])}</strong>);
        remaining = remaining.slice(boldMatch[0].length);
        continue;
      }

      // 6. Italique : *texte*
      const italicMatch = remaining.match(/^\*([^*]+)\*/);
      if (italicMatch) {
        nodes.push(<em key={`italic-${keyIdx++}`}>{renderInline(italicMatch[1])}</em>);
        remaining = remaining.slice(italicMatch[0].length);
        continue;
      }

      // 7. Balises HTML résiduelles
      const htmlTagMatch = remaining.match(/^<(\/?)(\w+)([^>]*?)>/);
      if (htmlTagMatch) {
        remaining = remaining.slice(htmlTagMatch[0].length);
        continue;
      }

      // Caractère standard jusqu'au prochain séparateur spécial
      const nextSpecial = remaining.search(/[!\[`<*]/);
      if (nextSpecial === -1) {
        nodes.push(remaining);
        break;
      } else if (nextSpecial === 0) {
        nodes.push(remaining[0]);
        remaining = remaining.slice(1);
      } else {
        nodes.push(remaining.slice(0, nextSpecial));
        remaining = remaining.slice(nextSpecial);
      }
    }

    return nodes;
  };

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      i++;
      continue;
    }

    // Séparateur horizontal
    if (/^---$|^___$|^\*\*\*$/.test(trimmed)) {
      elements.push(<hr key={`hr-${i}`} style={{ border: "none", borderTop: "1px solid var(--border-color)", margin: "16px 0" }} />);
      i++;
      continue;
    }

    // Titres #, ##, ###
    const h1Match = trimmed.match(/^#\s+(.+)$/);
    if (h1Match) {
      elements.push(
        <h1 key={`h1-${i}`} style={{ fontSize: "1.35rem", fontWeight: 800, margin: "14px 0 8px", color: "var(--text-main)" }}>
          {renderInline(h1Match[1])}
        </h1>
      );
      i++;
      continue;
    }

    const h2Match = trimmed.match(/^##\s+(.+)$/);
    if (h2Match) {
      elements.push(
        <h2 key={`h2-${i}`} style={{ fontSize: "1.15rem", fontWeight: 700, margin: "14px 0 6px", color: "var(--text-main)" }}>
          {renderInline(h2Match[1])}
        </h2>
      );
      i++;
      continue;
    }

    const h3Match = trimmed.match(/^###\s+(.+)$/);
    if (h3Match) {
      elements.push(
        <h3 key={`h3-${i}`} style={{ fontSize: "1rem", fontWeight: 700, margin: "10px 0 4px", color: "var(--text-main)" }}>
          {renderInline(h3Match[1])}
        </h3>
      );
      i++;
      continue;
    }

    // Blocs de code ```
    if (trimmed.startsWith("```")) {
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // Sauter la ligne de fermeture ```
      elements.push(
        <pre
          key={`code-block-${i}`}
          style={{
            background: "var(--bg-surface-elevated)",
            padding: "10px 12px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-color)",
            overflowX: "auto",
            fontSize: "0.82rem",
            margin: "8px 0",
            color: "var(--text-muted)",
          }}
        >
          <code>{codeLines.join("\n")}</code>
        </pre>
      );
      continue;
    }

    // Tableaux Markdown
    if (trimmed.startsWith("|") && trimmed.endsWith("|") && i + 1 < lines.length && lines[i + 1].includes("---")) {
      const headerRow = trimmed.slice(1, -1).split("|").map((c) => c.trim());
      i += 2; // Sauter en-tête + séparateur | :--- |

      const bodyRows: string[][] = [];
      while (i < lines.length && lines[i].trim().startsWith("|") && lines[i].trim().endsWith("|")) {
        const cols = lines[i].trim().slice(1, -1).split("|").map((c) => c.trim());
        bodyRows.push(cols);
        i++;
      }

      elements.push(
        <div key={`table-wrap-${i}`} style={{ overflowX: "auto", margin: "12px 0" }}>
          <table
            className="markdown-table"
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "0.85rem",
              background: "var(--bg-surface-elevated)",
              borderRadius: "var(--radius-sm)",
              overflow: "hidden",
              border: "1px solid var(--border-color)",
            }}
          >
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
      continue;
    }

    // Listes à puces
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      const listItems: string[] = [];
      while (i < lines.length && (lines[i].trim().startsWith("- ") || lines[i].trim().startsWith("* "))) {
        listItems.push(lines[i].trim().slice(2));
        i++;
      }
      elements.push(
        <ul key={`ul-${i}`} style={{ margin: "8px 0", paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "4px" }}>
          {listItems.map((it, idx) => (
            <li key={idx} style={{ color: "var(--text-main)", fontSize: "0.88rem", lineHeight: 1.5 }}>
              {renderInline(it)}
            </li>
          ))}
        </ul>
      );
      continue;
    }

    // Paragraphe normal
    elements.push(
      <p key={`p-${i}`} style={{ margin: "6px 0", lineHeight: 1.6, fontSize: "0.88rem", color: "var(--text-main)" }}>
        {renderInline(trimmed)}
      </p>
    );
    i++;
  }

  return <div className={`markdown-view ${className}`}>{elements}</div>;
}
