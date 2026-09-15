"use client";

import { useEffect } from "react";

/**
 * Redirection douce (réf. mission "supprimer la catégorie playlist du volet
 * ouvrant, déplacer la création de playlist vidéo dans Bibliothèque") : la
 * création de playlists vidéo vit désormais dans l'onglet "Playlists" de
 * `/library`. Cette page ne reste que pour ne pas casser un onglet déjà
 * ouvert ou un signet existant.
 *
 * `window.location.replace` plutôt que `redirect()`/`next.config.ts`
 * `redirects()` : l'app est un export statique Next (`output: "export"`,
 * réf. next.config.ts), sans serveur Next pour les gérer — même idiome que
 * `useDisplayOutputRedirect.ts`.
 */
export default function PlaylistsRedirectPage() {
  useEffect(() => {
    window.location.replace("/library/");
  }, []);
  return null;
}
