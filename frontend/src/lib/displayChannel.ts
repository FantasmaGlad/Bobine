/**
 * Identité de canal d'un écran de diffusion (câblé ou réseau) — logique PURE,
 * sans accès au DOM, pour rester testable (`frontend/tests/`).
 *
 * Pourquoi ce module : avant lui, `/cinema` déduisait son canal du NOM D'HÔTE
 * (127.0.0.1/localhost = câblé, tout le reste = réseau) tandis que `/kiosk` lisait
 * `?channel=` avec « câblé » par défaut, et la redirection kiosk/cinéma
 * supprimait ce paramètre. Résultat : sur une seule machine en 127.0.0.1, un
 * écran réglé « Réseau » était reclassé « câblé » dès sa première redirection
 * et ne pouvait jamais suivre le cours lancé dans le canal Réseau. Une seule
 * règle, partagée par toutes les pages de diffusion, supprime cette dérive.
 *
 * Règle (par ordre de priorité) :
 *  1. paramètre d'URL explicite `?channel=cable|network` (seul moyen fiable
 *     d'avoir un écran « Réseau » sur la machine du serveur, en 127.0.0.1) ;
 *  2. à défaut, le comportement historique PROPRE À LA PAGE (décision
 *     volontaire du commit 675e441, conservée) :
 *       - `/kiosk` = câblé (une TV sur IP LAN qui affiche /kiosk est un écran
 *         du canal câblé, pas un appareil « réseau ») ;
 *       - `/cinema` = heuristique sur le nom d'hôte : boucle locale = câblé
 *         (kiosque Chromium du Wyse, `Presentation` HDMI Android), tout autre
 *         hôte (IP LAN, mDNS, téléphone d'adhérent) = réseau.
 *
 * Le canal est rendu EXPLICITE dans l'URL dès la première redirection
 * (`buildOutputUrl`) : il ne dépend alors plus de la page qui le résout.
 */

export type DisplayChannel = "cable" | "network";

export type ChannelSource = "query" | "default";

export type DisplayPage = "kiosk" | "cinema";

export interface ResolvedChannel {
  channel: DisplayChannel;
  /** Origine de la décision : un canal posé explicitement par l'URL ne doit
   * jamais être « corrigé » par une heuristique. */
  source: ChannelSource;
}

/** Vrai pour l'hôte de la boucle locale (le navigateur tourne sur la machine
 * qui héberge le serveur). */
export function isLoopbackHost(hostname: string): boolean {
  return hostname === "127.0.0.1" || hostname === "localhost" || hostname === "[::1]" || hostname === "::1";
}

export function parseChannelParam(search: string): DisplayChannel | null {
  const value = new URLSearchParams(search).get("channel");
  return value === "cable" || value === "network" ? value : null;
}

export function resolveChannel(search: string, hostname: string, page: DisplayPage): ResolvedChannel {
  const explicit = parseChannelParam(search);
  if (explicit) return { channel: explicit, source: "query" };
  if (page === "kiosk") return { channel: "cable", source: "default" };
  return { channel: isLoopbackHost(hostname) ? "cable" : "network", source: "default" };
}

/**
 * URL de redirection kiosk <-> cinéma : CONSERVE la query string courante et
 * y pose le canal résolu de façon explicite (sans quoi chaque page retomberait
 * sur SON défaut et un écran pourrait changer de canal en changeant de page).
 * `search` est `window.location.search` (avec son « ? » éventuel).
 */
export function buildOutputUrl(target: DisplayPage, search: string, channel: DisplayChannel): string {
  const params = new URLSearchParams(search);
  params.set("channel", channel);
  return `/${target}?${params.toString()}`;
}

/**
 * Faut-il suivre immédiatement la sortie stockée au montage ? Seul le canal
 * câblé le fait (l'écran du Wyse doit démarrer dans le bon mode au boot) ; un
 * appareil du réseau ne suit que les bascules décidées EN DIRECT, pour ne pas
 * éjecter quelqu'un qui ouvre volontairement /cinema.
 */
export function shouldFollowInitialOutput(channel: DisplayChannel): boolean {
  return channel === "cable";
}

/**
 * Identifiant de CETTE page de diffusion auprès du serveur (clé du rôle
 * primaire, cf. ws_manager.py). Un identifiant PAR CHARGEMENT de page — jamais
 * persisté : stocké en `localStorage` il était commun à tous les onglets de la
 * même origine (127.0.0.1:8000) et le serveur les prenait tous pour le même
 * kiosque, donc tous « primaires ». Les reconnexions WebSocket d'une même page
 * réutilisent la valeur gardée en mémoire par l'appelant.
 */
export function createPageClientId(random: () => string = defaultRandomId): string {
  return `kiosk-${random()}`;
}

function defaultRandomId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
