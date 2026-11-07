/**
 * Couleur de texte/icône lisible posée sur l'accent plein du THÈME actif : le jeton `--accent-primary-fg`, calculé pour
 * chaque palette et chaque mode par `lib/themePalettes.ts` (contraste AA garanti, vérifié par les tests). Aucun calcul
 * ni lecture du DOM à l'exécution : la valeur suit le thème par la seule cascade CSS.
 */
export const THEME_ACCENT_FOREGROUND = "var(--accent-primary-fg)";

export function useThemeAccentForeground(): string {
  return THEME_ACCENT_FOREGROUND;
}
