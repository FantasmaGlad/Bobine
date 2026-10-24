/**
 * Canaux de diffusion (Stable, Bêta, Canary) et icônes qui leur sont associées dans
 * l'interface. Module unique : tout composant qui affiche une illustration ou une icône
 * de canal passe par ici, jamais par une URL écrite en dur.
 *
 * Les fichiers (/logo-<canal>.png, /favicon-<canal>.png) sont générés par
 * scripts/generate_channel_icons.py à partir de Assets/Images/channel-icons/ (guide :
 * le README de ce dossier). Ajouter un canal = l'ajouter ici, dans le générateur et dans
 * backend/app/utils/version.py ; backend/tests/test_channel_icons_wiring.py échoue si
 * une implémentation diverge.
 */

export const RELEASE_CHANNELS = ["stable", "beta", "canary"] as const;
export type UpdateChannel = (typeof RELEASE_CHANNELS)[number];
export const DEFAULT_RELEASE_CHANNEL: UpdateChannel = "stable";

export function isReleaseChannel(value: unknown): value is UpdateChannel {
  return typeof value === "string" && (RELEASE_CHANNELS as readonly string[]).includes(value);
}

/** Illustration du canal (mascotte, 512 px) : logo de l'application, sélecteur de canal. */
export function channelLogoUrl(channel: UpdateChannel): string {
  return `/logo-${channel}.png`;
}

/** Version réduite du canal pour l'onglet du navigateur. */
export function channelFaviconUrl(channel: UpdateChannel): string {
  return `/favicon-${channel}.png`;
}

/**
 * Pose le favicon du canal sur TOUS les `<link rel="icon">` existants (le navigateur n'en
 * retient qu'un et rien ne garantit lequel) ou en crée un s'il n'y en a aucun. Les
 * `apple-touch-icon` et l'icône du manifeste PWA restent statiques : une application
 * installée ne peut pas changer d'icône à chaud.
 */
export function applyChannelFavicon(
  doc: Pick<Document, "querySelectorAll" | "createElement" | "head">,
  channel: UpdateChannel,
): void {
  const url = channelFaviconUrl(channel);
  const links = Array.from(doc.querySelectorAll<HTMLLinkElement>('link[rel="icon"], link[rel="shortcut icon"]'));
  if (links.length === 0) {
    const created = doc.createElement("link");
    created.rel = "icon";
    doc.head.appendChild(created);
    links.push(created);
  }
  for (const link of links) {
    link.type = "image/png";
    link.removeAttribute("sizes");
    link.href = url;
  }
}
