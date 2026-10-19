import React from "react";
import { highlightSegments } from "@/lib/searchText";

/** Texte avec la recherche surlignée (accents et casse tolérés, texte d'origine conservé). */
export default function Highlight({ text, query }: { text: string; query: string }) {
  const segments = highlightSegments(text, query);
  if (segments.length === 1 && !segments[0].match) return <>{text}</>;
  return (
    <>
      {segments.map((segment, i) =>
        segment.match ? (
          <mark key={i} className="search-mark">
            {segment.text}
          </mark>
        ) : (
          <React.Fragment key={i}>{segment.text}</React.Fragment>
        ),
      )}
    </>
  );
}
