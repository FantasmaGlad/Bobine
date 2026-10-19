"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { clearCachesAndReload } from "@/lib/cacheReload";
import { createPageClientId, type DisplayOutput } from "@/lib/displayChannel";
import { type ClockAnchor } from "@/lib/playbackClock";
import { ServerClockSync } from "@/lib/serverClockSync";

export type PlaybackStateValue =
  | "waiting"
  | "playing"
  | "paused"
  | "coach_mode"
  | "offline"
  | "playlist_waiting"
  | "background";

export interface PlaybackVideo {
  id: number;
  title: string;
  duration_seconds: number | null;
  program?: string | null;
  release?: string | null;
  thumbnail_url?: string | null;
  thumbnail_path?: string | null;
  description?: string | null;
  audio_channels?: number | null;
  audio_codec?: string | null;
  fps?: number | null;
  bitrate_kbps?: number | null;
  width?: number | null;
  height?: number | null;
}

export interface PlaybackBackground {
  id: number;
  title: string;
  /** Fond figé (png/jpg/webp) plutôt qu'une boucle vidéo — rendu via <img>
   * côté kiosk. */
  is_image?: boolean;
}

export type AudioChainMode = "auto" | "timer" | "manual";

/** Représente aussi bien un cours audio isolé qu'une playlist audio lancée : une playlist est traitée côté serveur comme un cours
 * virtuel dont les pistes viennent de plusieurs cours (program=null dans ce
 * cas, faute de programme unique). */
export interface PlaybackAudioCourse {
  id: number;
  title: string;
  program: string | null;
  background_id: number | null;
}

export interface PlaybackAudioTrack {
  id: number;
  number: number | null;
  title: string;
  duration_seconds: number | null;
  /** Fond d'ambiance propre à CETTE piste au sein d'une playlist audio — absent/nul pour une
   * piste sans fond propre, qui affiche alors le fond du cours/playlist. */
  background_id?: number | null;
  background_title?: string | null;
  background_is_image?: boolean;
}

export interface PlaybackState {
  state: PlaybackStateValue;
  current_video: PlaybackVideo | null;
  /** Sous-titres choisis depuis l'admin : null = piste par défaut, "off" = aucune, sinon identifiant de piste. */
  subtitle?: number | "off" | null;
  position_seconds: number;
  volume: number;
  speed: number;
  playlist_id: number | null;
  playlist_name: string | null;
  playlist_items: PlaybackVideo[] | null;
  playlist_index: number | null;
  playlist_waiting_remaining: number | null;
  current_background: PlaybackBackground | null;
  current_audio_course: PlaybackAudioCourse | null;
  audio_tracks: PlaybackAudioTrack[] | null;
  audio_track_index: number | null;
  audio_playing: boolean;
  audio_position_seconds: number;
  audio_chain_mode: AudioChainMode;
  audio_chain_timer_seconds: number;
  audio_chain_wait_remaining: number | null;
  /** Ancre de l'horloge de lecture vidéo pilotée par le serveur : la position cible s'en déduit localement (cf. lib/playbackClock.ts).
   * Absente d'un backend plus ancien. */
  clock?: ClockAnchor | null;
  /** Ancre de l'horloge de la piste audio du mode coach. */
  audio_clock?: ClockAnchor | null;
}

export type PlaybackChannel = "cable" | "network";

/** Lecture locale rapportée par une page /cinema du canal : purement déclaratif, le serveur ne
 * fait que relayer — null tant qu'aucun rapport n'est arrivé. */
export interface CinemaRemoteState {
  title: string | null;
  program: string | null;
  position_seconds: number;
  duration_seconds: number;
  playing: boolean;
  video_id?: number | null;
  reported_at: number;
}

// "launch" : diffusé par
// /grid (écran de sélection découplé) pour lancer un video_id précis sur
// les /cinema du canal - jamais émis par le profil desktop existant.
/** Données additionnelles d'un ordre cinéma : titre/durée du cours, et — pour un cours
 * lancé par ordre — l'ancre d'horloge serveur et l'identifiant du cours qu'elle pilote. */
export interface CinemaCommandExtra {
  title?: string;
  duration_seconds?: number | null;
  clock?: ClockAnchor;
  clock_video_id?: number;
}

export type CinemaCommandAction = "play" | "pause" | "seek" | "stop" | "launch";

export interface PlaybackEvent {
  event: "state_change" | "position_tick";
  cause: string;
  client_ts?: number;
  channel?: PlaybackChannel;
  data: PlaybackState;
  // Présent uniquement sur cause "position_tick" : numéro de séquence incrémental propre au canal, jamais
  // réinitialisé — sert à détecter un tick perdu en silence côté client.
  tick_seq?: number;
}

const DEFAULT_STATE: PlaybackState = {
  state: "waiting",
  current_video: null,
  position_seconds: 0,
  volume: 100,
  speed: 1.0,
  playlist_id: null,
  playlist_name: null,
  playlist_items: null,
  playlist_index: null,
  playlist_waiting_remaining: null,
  current_background: null,
  current_audio_course: null,
  audio_tracks: null,
  audio_track_index: null,
  audio_playing: false,
  audio_position_seconds: 0,
  audio_chain_mode: "auto",
  audio_chain_timer_seconds: 20,
  audio_chain_wait_remaining: null,
  clock: null,
  audio_clock: null,
};

function getWsUrl(): string {
  if (typeof window === "undefined") return "";
  const isDevServer = window.location.port === "3000";
  const host = isDevServer ? "localhost:8001" : window.location.host;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${host}/ws/playback`;
}

function getApiUrl(path: string): string {
  if (typeof window === "undefined") return "";
  const isDevServer = window.location.port === "3000";
  return isDevServer ? `http://localhost:8001/api${path}` : `/api${path}`;
}

// Intervalle du filet de sécurité de resynchronisation : un `broadcast()` peut échouer
// silencieusement sans jamais faire tomber la connexion WebSocket — dans ce
// cas aucun `state_change` ne rattrape jamais l'état affiché. Ce re-fetch
// REST périodique recale l'état local sur l'état réel du serveur même quand
// aucun évènement WebSocket n'est perdu.
const RESYNC_INTERVAL_MS = 15000;

// Identifiant de CETTE page auprès du serveur (clé du rôle primaire, cf.
// ws_manager.py `_primary_client_id`) : créé une fois par chargement de page et
// gardé en mémoire — les reconnexions WebSocket de la page le réutilisent
// (reprise immédiate du rôle primaire), mais il n'est JAMAIS persisté. Stocké
// en `localStorage` (ancien comportement), il était commun à tous les onglets
// de la même origine : sur une seule machine en 127.0.0.1, deux onglets
// étaient pris pour le même kiosque et se déclaraient tous deux primaires.
let pageClientId: string | null = null;

function getPageKioskClientId(): string {
  if (typeof window === "undefined") return "";
  if (pageClientId === null) pageClientId = createPageClientId();
  return pageClientId;
}

/**
 * Connexion WebSocket partagée à l'état de lecture. Utilisée à la
 * fois par l'écran kiosk (qui pilote un <video> réel) et par les
 * télécommandes (qui ne font que refléter/commander l'état).
 *
 * @param onEvent  Callback appelé à chaque changement d'état reçu.
 * @param role     Rôle du client : "kiosk" pour un écran kiosk, omis pour
 *                 une télécommande/admin. Un kiosk envoie un message
 *                 d'identification à la connexion et reçoit en retour son
 *                 statut primaire/miroir.
 * @param channel  Canal de diffusion suivi par ce client : seuls les évènements
 *                 de CE canal sont appliqués, et chaque commande envoyée
 *                 porte ce canal — deux lectures totalement indépendantes.
 */
export function usePlaybackSocket(
  onEvent?: (evt: PlaybackEvent) => void,
  role?: "kiosk",
  channel: PlaybackChannel = "cable",
  onCinemaCommand?: (action: CinemaCommandAction, positionSeconds: number, videoId?: number, extra?: CinemaCommandExtra) => void,
) {
  const [state, setState] = useState<PlaybackState>(DEFAULT_STATE);
  const [connected, setConnected] = useState(false);
  // Dernier rapport de lecture cinéma du canal — affiché par les tableaux de bord.
  const [cinemaState, setCinemaState] = useState<CinemaRemoteState | null>(null);
  // Sortie active par CANAL de diffusion : "kiosk" ou "cinema" chacun. Poussée en temps réel par
  // l'évènement display_output ; null tant que la valeur initiale n'a pas
  // été chargée (évite une redirection intempestive au montage avant de
  // connaître la vraie valeur).
  // Le câblé peut aussi valoir "radio" (l'écran câblé devient un poste radio) ; le réseau
  // reste kiosk/cinéma (son poste radio s'ouvre par URL).
  const [displayOutputCable, setDisplayOutputCable] = useState<DisplayOutput | null>(null);
  const [displayOutputNetwork, setDisplayOutputNetwork] = useState<"kiosk" | "cinema" | null>(null);
  // Verrou du mode cinéma : vrai brièvement après
  // qu'un "load"/"load_playlist" manuel a été rejeté par le backend, pour
  // que l'admin affiche un avertissement. Se réinitialise seul.
  const [cinemaLocked, setCinemaLocked] = useState(false);
  const cinemaLockedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // isPrimary : vrai si ce kiosk est le kiosk primaire (seul autorisé à
  // envoyer report_position). Toujours false pour les télécommandes/admin.
  const [isPrimary, setIsPrimary] = useState(false);
  // incrémenté à chaque `library_change` reçu (vidéo importée/modifiée/
  // supprimée) — une page consommatrice (grid/cinema/library) l'ajoute
  // en dépendance d'effet pour recharger sa liste sans attendre le
  // prochain sondage périodique.
  const [libraryVersion, setLibraryVersion] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  // Détection d'un flux silencieux (mesuré en conditions réelles) :
  // sur un Wi-Fi réel vers la tablette, le flux de position_tick peut
  // s'arrêter SILENCIEUSEMENT après quelques secondes — ni erreur ni
  // fermeture propre de la connexion des deux côtés, juste plus aucune
  // donnée qui circule. Sans détection dédiée, le client ne s'en aperçoit
  // qu'au keepalive serveur (jusqu'à 90s : 30s d'intervalle de ping + 60s
  // de tolérance de pong, volontairement assouplis pour tolérer les pages
  // en arrière-plan) — bien trop long pour un tableau de bord ACTIF que
  // l'admin regarde. Ce ref suit l'heure du DERNIER message reçu, tous
  // types confondus (y compris les ping serveur).
  const lastMessageAtRef = useRef(Date.now());
  // Commandes émises pendant une (re)connexion, rejouées à l'ouverture si
  // récentes (< 5 s) — voir sendCommand.
  const pendingCommandsRef = useRef<{ payload: string; queuedAt: number }[]>([]);
  // Détection d'un backend redémarré depuis le chargement de CETTE page : null
  // jusqu'au premier "boot_id" reçu (valeur de référence pour cette page) ;
  // une valeur DIFFÉRENTE à une reconnexion ultérieure signale que le backend
  // a redémarré entre-temps (reboot machine, watchdog, crash...) — l'écran ne
  // faisait jusqu'ici que reconnecter son WebSocket, en gardant en mémoire son
  // ancien bundle JS/HTML au lieu de se recharger comme le fait le bouton
  // « Synchronisation des écrans ».
  const bootIdRef = useRef<string | null>(null);
  // Dernier `tick_seq` de `position_tick` reçu pour ce canal : null tant qu'aucun tick n'est arrivé
  // sur la connexion courante — un écart
  // (`tick_seq` reçu > dernier + 1) signale un tick perdu en silence, plus
  // fréquent sur un Wi-Fi imparfait qu'une vraie coupure de connexion (auquel
  // cas `onclose`/le chien de garde de silence ci-dessous s'en chargent déjà).
  // Dans ce cas on ne peut pas attendre le prochain cycle du filet de
  // sécurité périodique (15s, cf. RESYNC_INTERVAL_MS) : `doResyncRef`
  // déclenche une resynchronisation REST immédiate.
  const lastTickSeqRef = useRef<number | null>(null);
  // Mesure du décalage d'horloge avec le serveur : partagée
  // avec la radio (lib/serverClockSync.ts).
  const clockSyncRef = useRef(new ServerClockSync());
  const doResyncRef = useRef<() => void>(() => {});
  const onEventRef = useRef(onEvent);
  const onCinemaCommandRef = useRef(onCinemaCommand);
  // Miroir de `state` lisible en dehors du cycle de rendu React (correctif
  // "kiosk miroir figé") : le filet de sécurité REST ci-dessous compare
  // l'état serveur à ce qu'affiche VRAIMENT ce client pour décider s'il doit
  // réappliquer les données au <video> — comparer à `state` directement
  // capturerait une valeur obsolète (closure du premier rendu de l'effet).
  const stateRef = useRef<PlaybackState>(DEFAULT_STATE);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    onCinemaCommandRef.current = onCinemaCommand;
  }, [onCinemaCommand]);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout>;
    // Backoff exponentiel (1s -> 2s -> 4s ... plafonné à 30s) : évite de
    // marteler le backend de tentatives de reconnexion en cas de coupure
    // prolongée. Réinitialisé à
    // chaque connexion réussie.
    let retryDelay = 1000;
    const MAX_RETRY_DELAY = 30000;

    const connect = () => {
      if (cancelled) return;
      const ws = new WebSocket(getWsUrl());
      wsRef.current = ws;

      const sendIdentify = () => {
        if (wsRef.current !== ws || ws.readyState !== WebSocket.OPEN) return;
        ws.send(JSON.stringify({
          command: "identify",
          params: { role: "kiosk", channel, client_id: getPageKioskClientId() },
        }));
      };

      ws.onopen = () => {
        // Garde-fou "socket fantôme" (correctif "le bouton Stop ne marche
        // plus après une reconnexion") : si une connexion PRÉCÉDENTE encore
        // en cours d'établissement ouvre APRÈS avoir été remplacée par une
        // plus récente (StrictMode en dev, ou vrai aléa réseau en prod —
        // Wi-Fi qui coupe puis reprend sur un mobile), ses callbacks
        // continuaient jusqu'ici à écraser l'état partagé alors qu'elle
        // n'est plus la connexion réellement utilisée par sendCommand().
        if (wsRef.current !== ws) return;
        setConnected(true);
        retryDelay = 1000;
        lastMessageAtRef.current = Date.now();
        // Nouvelle connexion : aucun tick de référence pour détecter un
        // écart tant que le premier n'est pas arrivé (évite un faux
        // positif comparant à un `tick_seq` d'une connexion précédente).
        lastTickSeqRef.current = null;
        clockSyncRef.current.start(ws, () => wsRef.current === ws);
        // Abonnement de canal : le serveur n'enverra plus à
        // cette connexion les évènements propres aux AUTRES canaux (le tri
        // client `parsed.channel !== channel` reste en filet de sécurité).
        ws.send(JSON.stringify({ command: "subscribe", params: { channels: [channel] } }));
        // Identification du rôle kiosk : envoyée dès
        // l'ouverture de la connexion pour que le backend puisse assigner
        // le rôle primaire/miroir avant tout report_position. Pas de
        // renouvellement périodique nécessaire : le rôle primaire, côté
        // backend, n'expire plus jamais tout seul (cf. ws_manager.py) — il
        // n'est repris que sur une vraie déconnexion, auquel cas le backend
        // pousse lui-même "promoted_primary" (cf. plus bas) pour déclencher
        // un nouvel identify immédiat.
        if (role === "kiosk") {
          sendIdentify();
        }
        // Rejoue les commandes mises en file pendant la coupure (voir
        // sendCommand) — uniquement les fraîches, dans l'ordre d'émission.
        const now = Date.now();
        const pending = pendingCommandsRef.current.filter((p) => now - p.queuedAt < 5000);
        pendingCommandsRef.current = [];
        for (const p of pending) ws.send(p.payload);
      };

      ws.onmessage = (evt) => {
        if (wsRef.current !== ws) return;
        lastMessageAtRef.current = Date.now();
        try {
          const parsed = JSON.parse(evt.data);
          if (parsed.event === "ping") {
            // Keepalive serveur : répondre immédiatement
            // pour signaler que cette connexion est toujours vivante.
            ws.send(JSON.stringify({ command: "pong" }));
            return;
          }
          if (clockSyncRef.current.handleMessage(parsed)) return;
          if (parsed.event === "boot_id") {
            if (bootIdRef.current === null) {
              bootIdRef.current = parsed.boot_id;
            } else if (bootIdRef.current !== parsed.boot_id) {
              // Le backend a redémarré depuis le chargement de cette page :
              // même traitement que "force_reload" (vide les caches, recharge).
              void clearCachesAndReload();
            }
            return;
          }
          if (parsed.event === "kiosk_role") {
            // Le backend nous indique si nous sommes kiosk primaire ou miroir.
            setIsPrimary(!!parsed.is_primary);
            return;
          }
          if (parsed.event === "promoted_primary") {
            // Le kiosk primaire du canal s'est déconnecté et a libéré son
            // rôle — on retente immédiatement notre identify pour le
            // réclamer sans délai ; le backend confirmera via "kiosk_role".
            sendIdentify();
            return;
          }
          if (parsed.event === "display_output") {
            // Bascule kiosk/cinéma décidée depuis l'admin, par canal : chaque
            // page (kiosk, cinema) décide elle-même si elle doit naviguer,
            // selon qu'elle tourne sur l'écran câblé ou sur le réseau.
            if (parsed.channel === "cable" && (parsed.output === "kiosk" || parsed.output === "cinema" || parsed.output === "radio")) {
              setDisplayOutputCable(parsed.output);
            } else if (parsed.channel === "network" && (parsed.output === "kiosk" || parsed.output === "cinema")) {
              setDisplayOutputNetwork(parsed.output);
            }
            return;
          }
          if (parsed.event === "command_rejected") {
            // Verrou du mode cinéma : le backend
            // a ignoré un "load"/"load_playlist" manuel car la sortie
            // câblée est en mode cinéma. N'arrive qu'au client émetteur (pas
            // de broadcast), donc uniquement pertinent pour l'admin qui a
            // cliqué "Lancer".
            if (parsed.reason === "cinema_locked") {
              setCinemaLocked(true);
              if (cinemaLockedTimerRef.current) clearTimeout(cinemaLockedTimerRef.current);
              cinemaLockedTimerRef.current = setTimeout(() => setCinemaLocked(false), 5000);
            }
            return;
          }
          if (parsed.event === "cinema_state") {
            // Rapport d'une page /cinema du canal : simple reflet pour les tableaux
            // de bord, filtré par canal comme les états de lecture.
            if ((parsed.channel ?? "cable") !== channel) return;
            setCinemaState(parsed.data ?? null);
            return;
          }
          if (parsed.event === "cinema_command") {
            // Ordre admin appliqué par les pages /cinema du canal.
            if ((parsed.channel ?? "cable") !== channel) return;
            onCinemaCommandRef.current?.(
              parsed.action,
              parsed.position_seconds ?? 0,
              parsed.video_id ?? undefined,
              { title: parsed.title, duration_seconds: parsed.duration_seconds, clock: parsed.clock, clock_video_id: parsed.clock_video_id }
            );
            return;
          }
          if (parsed.event === "library_change") {
            // eslint-disable-next-line react-hooks/set-state-in-effect -- réaction à un évènement externe temps réel
            setLibraryVersion((v) => v + 1);
            return;
          }
          if (parsed.event === "force_reload") {
            // Bouton « Synchronisation des écrans » (Paramètres) : vide les
            // caches de l'appareil PUIS recharge, pour reprendre à zéro (état
            // React, connexion WebSocket) ET re-télécharger les nouveaux
            // assets au lieu de resservir d'anciennes versions cachées.
            void clearCachesAndReload();
            return;
          }
          if (parsed.event === "state_change" || parsed.event === "position_tick") {
            // Filtrage par canal : le serveur diffuse les évènements des DEUX canaux
            // sur la même connexion, chacun étiqueté — ce client n'applique
            // que ceux de SON canal. Absence de champ = message d'une
            // version antérieure du backend → canal câblé.
            if ((parsed.channel ?? "cable") !== channel) return;
            if (parsed.cause === "position_tick" && typeof parsed.tick_seq === "number") {
              const previous = lastTickSeqRef.current;
              if (previous !== null && parsed.tick_seq > previous + 1) {
                // Trou détecté (des ticks intermédiaires n'ont jamais
                // atteint ce client, silencieusement) : ne pas attendre le
                // prochain cycle du filet de sécurité périodique.
                doResyncRef.current();
              }
              lastTickSeqRef.current = parsed.tick_seq;
            }
            setState(parsed.data);
            onEventRef.current?.(parsed as PlaybackEvent);
          }
        } catch (err) {
          console.error("Message WebSocket playback invalide", err);
        }
      };

      ws.onclose = () => {
        clockSyncRef.current.stop();
        // Même garde-fou qu'à l'ouverture : une connexion déjà remplacée qui
        // se ferme tardivement ne doit ni toucher l'état partagé, ni
        // programmer une seconde reconnexion concurrente à celle éventuelle
        // de la connexion réellement active.
        if (wsRef.current !== ws) return;
        setConnected(false);
        setIsPrimary(false);
        wsRef.current = null;
        if (!cancelled) {
          reconnectTimer = setTimeout(connect, retryDelay);
          retryDelay = Math.min(retryDelay * 2, MAX_RETRY_DELAY);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    // un onglet/WebView en
    // arrière-plan voit ses minuteurs JS throttlés par le navigateur (jusqu'à
    // 1 réveil/minute) — le `pong` de réponse au `ping` serveur peut alors
    // arriver tard ou pas du tout tant que la page reste cachée, ce qui la
    // faisait fermer côté serveur (cf. PONG_TIMEOUT_SECONDS, assoupli en
    // complément côté serveur). `visibilitychange` se déclenche lui de façon
    // fiable et IMMÉDIATE dès que l'utilisateur revient sur cette page,
    // indépendamment de tout minuteur throttlé — un pong proactif à cet
    // instant referme la fenêtre avant que le serveur n'ait eu la moindre
    // raison de couper la connexion.
    const onVisible = () => {
      if (typeof document === "undefined" || document.visibilityState !== "visible") return;
      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ command: "pong" }));
      }
    };
    if (typeof document !== "undefined") {
      document.addEventListener("visibilitychange", onVisible);
    }

    // Chien de garde de silence : `readyState === OPEN` ne garantit PAS que des données
    // circulent encore — mesuré en conditions réelles sur Wi-Fi, la
    // connexion peut rester "ouverte" au sens du navigateur alors que plus
    // rien n'est réellement délivré dans un sens ou l'autre, sans jamais
    // déclencher `onclose`/`onerror`. Seuil COURT (5s) pendant une lecture
    // active — la cadence normale de `position_tick` est de 250 ms à 2 s,
    // 5 s de silence total y est déjà anormal — et seuil LONG (35s, un peu
    // plus que `PING_INTERVAL_SECONDS` côté serveur) au repos, pour ne
    // jamais déclencher à tort entre deux ping normaux. Ne fait rien tant
    // que la page est en arrière-plan (ses minuteurs sont de toute façon
    // throttlés, et rien n'y est activement regardé) — `onVisible`
    // ci-dessus reprend la main dès le retour au premier plan.
    const STALE_THRESHOLD_ACTIVE_MS = 5000;
    const STALE_THRESHOLD_IDLE_MS = 35000;
    const staleWatchdog = setInterval(() => {
      if (typeof document !== "undefined" && document.visibilityState !== "visible") return;
      const current = wsRef.current;
      if (!current || current.readyState !== WebSocket.OPEN) return;
      const isActivelyPlaying =
        stateRef.current.state === "playing" || stateRef.current.audio_playing;
      const threshold = isActivelyPlaying ? STALE_THRESHOLD_ACTIVE_MS : STALE_THRESHOLD_IDLE_MS;
      if (Date.now() - lastMessageAtRef.current > threshold) {
        // Force une reconnexion propre plutôt que d'attendre le keepalive
        // serveur : ferme CETTE connexion, `onclose` (déjà en place)
        // programme la reconnexion avec son propre backoff.
        current.close();
      }
    }, 2000);

    return () => {
      cancelled = true;
      clearTimeout(reconnectTimer);
      clearInterval(staleWatchdog);
      if (cinemaLockedTimerRef.current) clearTimeout(cinemaLockedTimerRef.current);
      if (typeof document !== "undefined") {
        document.removeEventListener("visibilitychange", onVisible);
      }
      wsRef.current?.close();
    };
  }, [role, channel]);

  // Filet de sécurité de resynchronisation périodique : indépendant du cycle de vie de la
  // connexion WebSocket ci-dessus. Recale l'état local sur `GET
  // /api/playback/state` à intervalle régulier, pour rattraper un
  // `broadcast()` perdu côté serveur sans que la connexion WebSocket
  // elle-même n'ait jamais été coupée — dans ce cas aucun `state_change` de
  // rattrapage n'arriverait jamais autrement.
  useEffect(() => {
    let cancelled = false;
    const resync = () => {
      if (cancelled) return;
      fetch(getApiUrl(`/playback/state?channel=${channel}`), { cache: "no-store" })
        .then((res) => (res.ok ? res.json() : null))
        .then((data: PlaybackState | null) => {
          if (cancelled || !data) return;
          if (JSON.stringify(stateRef.current) === JSON.stringify(data)) return;
          setState(data);
          // Correctif "kiosk miroir figé" : jusqu'ici ce filet de sécurité
          // mettait à jour `state` (l'affichage textuel) mais n'appelait
          // jamais `onEvent` — le <video> du kiosk n'était donc JAMAIS
          // corrigé par ce chemin. Un `state_change` perdu (reconnexion
          // WebSocket manquée) laissait alors la vidéo figée sur
          // sa dernière position connue indéfiniment, jusqu'au prochain
          // évènement WebSocket qui pouvait ne jamais arriver. On rejoue donc
          // ici un évènement "sync" synthétique, exactement comme au premier
          // rattachement de la connexion WebSocket.
          onEventRef.current?.({ event: "state_change", cause: "sync", data });
        })
        .catch(() => {
          // Pas de réseau/serveur injoignable : la reconnexion WebSocket
          // gère déjà ce cas, rien à faire de plus ici.
        });
    };
    // Exposée hors de cet effet :
    // la détection de trou dans les `position_tick`, gérée par l'effet de
    // connexion WebSocket ci-dessus, appelle cette MÊME fonction pour une
    // resynchronisation immédiate au lieu d'attendre `RESYNC_INTERVAL_MS`.
    doResyncRef.current = resync;
    const id = setInterval(resync, RESYNC_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
      doResyncRef.current = () => {};
    };
  }, [channel]);

  // Valeurs initiales des deux canaux : chargées une fois au montage, les
  // changements suivants arrivent en push via l'évènement display_output.
  useEffect(() => {
    let cancelled = false;
    fetch(getApiUrl("/settings/display-output"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        if (data.cable === "kiosk" || data.cable === "cinema" || data.cable === "radio") {
          setDisplayOutputCable((prev) => prev ?? data.cable);
        }
        if (data.network === "kiosk" || data.network === "cinema") {
          setDisplayOutputNetwork((prev) => prev ?? data.network);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  /** Heure serveur estimée (epoch, ms) : horloge locale + décalage mesuré. */
  const serverNow = useCallback(() => clockSyncRef.current.serverNow(), []);

  const sendCommand = useCallback((command: string, params: Record<string, unknown> = {}) => {
    const ws = wsRef.current;
    // Chaque commande porte son canal cible : le serveur route vers le
    // gestionnaire d'état du bon canal (zéro interférence entre les deux).
    const payload = JSON.stringify({ command, params: { channel, ...params, client_ts: Date.now() } });
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(payload);
      return;
    }
    // File d'attente courte : pendant une (re)connexion — fréquent sur téléphone dont le
    // Wi-Fi se rendort/reprend — les commandes étaient jetées SILENCIEUSEMENT,
    // le bouton semblait juste ne rien faire. On mémorise la commande avec
    // son heure d'émission et la boucle de connexion la rejoue à l'ouverture
    // si elle a moins de 5 s (au-delà, rejouer un play/pause périmé ferait
    // pire que de le perdre).
    pendingCommandsRef.current.push({ payload, queuedAt: Date.now() });
    if (pendingCommandsRef.current.length > 10) pendingCommandsRef.current.shift();
  }, [channel]);

  return {
    state, connected, sendCommand, serverNow, isPrimary, displayOutputCable, displayOutputNetwork,
    cinemaLocked, cinemaState, libraryVersion,
  };
}

