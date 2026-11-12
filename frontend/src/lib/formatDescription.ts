export function formatCleanDescription(desc?: string | null): string {
  if (!desc) return "";
  const norm = desc.replace(/\r\n/g, "\n").trim();
  if (norm.includes("\n\n")) {
    return norm
      .split(/\n\s*\n/)
      .map((p) => p.replace(/\s*\n\s*/g, " ").replace(/[ \t]+/g, " ").trim())
      .filter(Boolean)
      .join("\n\n");
  }
  const lines = norm.split("\n").map((l) => l.trim()).filter(Boolean);
  const paragraphs: string[] = [];
  let currentBuffer = "";

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!currentBuffer) {
      currentBuffer = line;
    } else {
      const endsWithSentencePunct = /[.!?]$/.test(currentBuffer);
      const nextStartsLower = /^[a-zà-öø-ÿ]/.test(line);

      if (!endsWithSentencePunct || nextStartsLower) {
        if (currentBuffer.endsWith("-")) {
          currentBuffer = currentBuffer.slice(0, -1) + line;
        } else {
          currentBuffer = currentBuffer + " " + line;
        }
      } else {
        paragraphs.push(currentBuffer);
        currentBuffer = line;
      }
    }
  }
  if (currentBuffer) {
    paragraphs.push(currentBuffer);
  }

  return paragraphs
    .map((p) => p.replace(/[ \t]+/g, " ").trim())
    .filter(Boolean)
    .join("\n\n");
}
