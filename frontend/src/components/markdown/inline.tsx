import React from "react";
import { isServedImage, safeLinkUrl } from "@/lib/safeUrl";

type Step = { nodes: React.ReactNode[]; rest: string };
type Rule = (text: string, nextKey: () => number) => Step | null;

const IMAGE_STYLE = { display: "inline-block", verticalAlign: "middle", maxWidth: "100%", margin: "2px 4px" } as const;
const CODE_STYLE = {
  background: "var(--bg-surface-elevated)",
  padding: "2px 6px",
  borderRadius: "4px",
  fontSize: "0.85em",
  fontFamily: "monospace",
  color: "var(--accent-text)",
  border: "1px solid var(--border-color)",
} as const;

const markdownImage: Rule = (text, nextKey) => {
  const match = text.match(/^!\[(.*?)\]\((.*?)\)/);
  if (!match) return null;
  const [whole, alt, src] = match;
  const rest = text.slice(whole.length);
  if (!isServedImage(src)) return { nodes: alt ? [alt] : [], rest };
  return { nodes: [<img key={`img-${nextKey()}`} src={src} alt={alt} style={IMAGE_STYLE} loading="lazy" />], rest };
};

const htmlImage: Rule = (text, nextKey) => {
  const match = text.match(/^<img\s+([^>]*?)src=["'](.*?)["']([^>]*?)\/?>/i);
  if (!match) return null;
  const src = match[2];
  const rest = text.slice(match[0].length);
  if (!isServedImage(src)) {
    const alt = match[0].match(/alt=["'](.*?)["']/i)?.[1];
    return { nodes: alt ? [alt] : [], rest };
  }
  return { nodes: [<img key={`himg-${nextKey()}`} src={src} alt="" style={IMAGE_STYLE} loading="lazy" />], rest };
};

const link: Rule = (text, nextKey) => {
  const match = text.match(/^\[(.*?)\]\((.*?)\)/);
  if (!match) return null;
  const linkText = match[1];
  const linkUrl = safeLinkUrl(match[2]);
  const rest = text.slice(match[0].length);
  if (!linkUrl) return { nodes: renderInline(linkText), rest };
  return {
    nodes: [
      <a key={`link-${nextKey()}`} href={linkUrl} target="_blank" rel="noopener noreferrer"
        style={{ color: "var(--accent-text)", fontWeight: 600, textDecoration: "underline" }}>
        {renderInline(linkText)}
      </a>,
    ],
    rest,
  };
};

const code: Rule = (text, nextKey) => {
  const match = text.match(/^`([^`]+)`/);
  if (!match) return null;
  return { nodes: [<code key={`code-${nextKey()}`} style={CODE_STYLE}>{match[1]}</code>], rest: text.slice(match[0].length) };
};

const bold: Rule = (text, nextKey) => {
  const match = text.match(/^\*\*([^*]+)\*\*/);
  if (!match) return null;
  return { nodes: [<strong key={`bold-${nextKey()}`}>{renderInline(match[1])}</strong>], rest: text.slice(match[0].length) };
};

const italic: Rule = (text, nextKey) => {
  const match = text.match(/^\*([^*]+)\*/);
  if (!match) return null;
  return { nodes: [<em key={`italic-${nextKey()}`}>{renderInline(match[1])}</em>], rest: text.slice(match[0].length) };
};

const htmlTag: Rule = (text) => {
  const match = text.match(/^<(\/?)(\w+)([^>]*?)>/);
  return match ? { nodes: [], rest: text.slice(match[0].length) } : null;
};

const RULES = [markdownImage, htmlImage, link, code, bold, italic, htmlTag];

function plainText(text: string): Step {
  const nextSpecial = text.search(/[!\[`<*]/);
  if (nextSpecial === -1) return { nodes: [text], rest: "" };
  if (nextSpecial === 0) return { nodes: [text[0]], rest: text.slice(1) };
  return { nodes: [text.slice(0, nextSpecial)], rest: text.slice(nextSpecial) };
}

export function renderInline(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  let remaining = text;
  let keyIdx = 0;
  const nextKey = () => keyIdx++;
  while (remaining.length > 0) {
    let step: Step | null = null;
    for (const rule of RULES) {
      step = rule(remaining, nextKey);
      if (step) break;
    }
    step ??= plainText(remaining);
    nodes.push(...step.nodes);
    remaining = step.rest;
  }
  return nodes;
}
