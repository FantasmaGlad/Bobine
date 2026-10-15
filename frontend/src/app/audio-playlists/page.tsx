"use client";

import { useEffect } from "react";

/**
 * Redirection douce : la création d'éditions mixées vit désormais dans l'onglet
 * "Playlists" de `/audio`. Cette page ne reste que pour ne pas casser un
 * onglet déjà ouvert ou un signet existant.
 *
 * `window.location.replace` plutôt que `redirect()`/`next.config.ts`
 * `redirects()` : l'app est un export statique Next (`output: "export"`,
 * voir next.config.ts), sans serveur Next pour les gérer — même idiome que
 * `useDisplayOutputRedirect.ts`.
 */
export default function AudioPlaylistsRedirectPage() {
  useEffect(() => {
    window.location.replace("/audio/");
  }, []);
  return null;
}
