"use client";

import React from "react";
import { parseBlock } from "./markdown/blocks";

interface MarkdownViewProps {
  content: string;
  className?: string;
}

export default function MarkdownView({ content, className = "" }: MarkdownViewProps) {
  if (!content) return null;
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const elements: React.ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const trimmed = lines[i].trim();
    if (!trimmed) {
      i++;
      continue;
    }
    const { node, next } = parseBlock(lines, i, trimmed);
    elements.push(node);
    i = next;
  }
  return <div className={`markdown-view ${className}`}>{elements}</div>;
}
