const FULLSCREEN_PATHS = ["/kiosk", "/cinema", "/coach", "/grid", "/radio"];

export function isFullscreenPath(pathname: string | null | undefined): boolean {
  if (!pathname) return false;
  const normalized = pathname.length > 1 && pathname.endsWith("/") ? pathname.slice(0, -1) : pathname;
  return FULLSCREEN_PATHS.includes(normalized);
}
