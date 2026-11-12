export async function copyText(text: string): Promise<boolean> {
  if (typeof window !== "undefined" && window.isSecureContext && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
    }
  }
  return copyWithSelection(text);
}

function copyWithSelection(text: string): boolean {
  if (typeof document === "undefined" || !document.body) return false;
  const previouslyFocused = document.activeElement as HTMLElement | null;
  const field = document.createElement("textarea");
  field.value = text;
  field.setAttribute("readonly", "");
  field.setAttribute("aria-hidden", "true");
  field.style.cssText = "position:fixed;top:0;left:-9999px;width:1px;height:1px;opacity:0;";
  document.body.appendChild(field);
  try {
    field.focus();
    field.select();
    field.setSelectionRange(0, text.length);
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    document.body.removeChild(field);
    previouslyFocused?.focus?.();
  }
}
