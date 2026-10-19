/**
 * Pages plein écran (sans barre latérale d'administration) : écrans de diffusion et
 * d'attente destinés à être ouverts sur un autre appareil ou sur une sortie physique.
 * Logique PURE, testable (`frontend/tests/`).
 *
 * La comparaison porte sur le `pathname` EXACT, jamais sur un préfixe : `/radio` est un
 * poste de diffusion, mais `/radio-library`, `/radio-remote` et `/radio-announcements`
 * restent des pages d'administration normales. Les paramètres de requête ne font pas partie
 * du `pathname` : `/radio?channel=cable` et `/radio?channel=network` sont donc plein écran
 * au même titre que `/radio` nu.
 */
const FULLSCREEN_PATHS = ["/kiosk", "/cinema", "/coach", "/grid", "/radio"];

export function isFullscreenPath(pathname: string | null | undefined): boolean {
  if (!pathname) return false;
  const normalized = pathname.length > 1 && pathname.endsWith("/") ? pathname.slice(0, -1) : pathname;
  return FULLSCREEN_PATHS.includes(normalized);
}
