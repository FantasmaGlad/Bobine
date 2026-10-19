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
 *         hôte (IP LAN, mDNS, téléphone d'adhérent) = réseau ;
 *       - `/radio` = RÉSEAU, quel que soit l'hôte : `/radio` nu a toujours été
 *         le poste radio réseau (favoris, onglets déjà ouverts). Aucune
 *         heuristique de nom d'hôte pour la radio — la sortie câblée s'ouvre
 *         explicitement par `/radio?channel=cable`.
 *
 * Le canal est rendu EXPLICITE dans l'URL dès la première redirection
 * (`buildOutputUrl`) : il ne dépend alors plus de la page qui le résout.
 */

export type DisplayChannel = "cable" | "network";

export type ChannelSource = "query" | "default";

export type DisplayPage = "kiosk" | "cinema" | "radio";

/** Sortie affichée par un canal de diffusion : seul le câblé peut être basculé sur la
 * radio (l'écran physique devient un poste radio) ; le réseau a déjà son poste par URL. */
export type DisplayOutput = "kiosk" | "cinema" | "radio";

/** Identifiant d'une sortie radio côté serveur : un moteur INDÉPENDANT par sortie. */
export type RadioChannelId = "radio_cable" | "radio_network";

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
  if (page === "radio") return { channel: "network", source: "default" };
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
export function shouldFollowInitialOutput(channel: DisplayChannel, page: DisplayPage = "kiosk"): boolean {
  // La page radio ne suit QUE les bascules faites en direct : /radio?channel=cable ouvert à
  // la main sur un autre appareil ne doit pas être éjecté vers /kiosk au montage (le
  // kiosque du Wyse, lui, arrive par /kiosk et est redirigé vers la radio).
  if (page === "radio") return false;
  return channel === "cable";
}

/** Moteur radio (côté serveur) correspondant à la sortie de diffusion d'un écran. */
export function radioChannelId(channel: DisplayChannel): RadioChannelId {
  return channel === "cable" ? "radio_cable" : "radio_network";
}

export interface OutputRedirectDecision {
  /** Nouvelle « dernière valeur observée » pour le canal de cet appareil. */
  seen: DisplayOutput | null;
  /** URL de destination, ou null si la page doit rester où elle est. */
  to: string | null;
}

/**
 * Faut-il quitter la page courante pour suivre la sortie choisie par l'admin ? Logique
 * PURE (testable) extraite du hook `useDisplayOutputRedirect`.
 *
 * - `previous` : dernière valeur observée (null = valeur initiale tout juste chargée).
 * - Seul le câblé peut viser la radio ; une cible radio sur un autre canal est ignorée.
 * - Un poste radio RÉSEAU ne suit jamais rien (c'est un lecteur dédié, pas un écran de
 *   cours) ; un poste radio câblé quitte la page quand l'admin repasse en kiosk/cinéma.
 */
export function decideOutputRedirect(
  current: DisplayPage,
  search: string,
  hostname: string,
  cableOutput: DisplayOutput | null,
  networkOutput: DisplayOutput | null,
  previous: DisplayOutput | null,
): OutputRedirectDecision {
  const { channel } = resolveChannel(search, hostname, current);
  const target = channel === "cable" ? cableOutput : networkOutput;
  if (!target) return { seen: previous, to: null };

  const seen = target;
  if (target === "radio" && channel !== "cable") return { seen, to: null };
  if (current === "radio" && channel !== "cable") return { seen, to: null };
  if (target === current) return { seen, to: null };
  // Un poste radio câblé ne repart que d'une sortie où il se trouvait EN PHASE (radio) : ouvert
  // à la main alors que l'écran câblé est en kiosk, il ne suit pas les bascules kiosk <-> cinéma.
  if (current === "radio" && previous !== "radio") return { seen, to: null };
  if (!shouldFollowInitialOutput(channel, current) && previous === null) return { seen, to: null };
  return { seen, to: buildOutputUrl(target, search, channel) };
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
