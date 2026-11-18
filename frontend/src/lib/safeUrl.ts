export function safeLinkUrl(url: string): string | null {
  const value = url.trim();
  return /^https?:\/\//i.test(value) ? value : null;
}

export function isServedImage(src: string): boolean {
  const value = src.trim();
  return (value.startsWith("/") && !value.startsWith("//")) || /^data:image\//i.test(value);
}
