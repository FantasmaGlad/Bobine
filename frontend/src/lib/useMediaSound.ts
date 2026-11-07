"use client";

import { useEffect, type RefObject } from "react";
import { createSoundChain, type SoundChain } from "./radioSoundGraph";
import { isNeutralSound, type RadioSoundSettings } from "./radioSound";

/**
 * Applique les réglages de son d'un canal (égaliseur, basses, loudness, limiteur) à un `<video>` ou `<audio>` par un
 * graphe Web Audio : élément → chaîne de la radio → sortie.
 *
 * Règles de sûreté :
 *  - Rien n'est branché tant que les réglages ne changent pas le son : le son direct de l'élément reste intact.
 *  - `createMediaElementSource` est définitif (l'élément ne sort plus que par le graphe). On ne l'appelle donc que si
 *    l'`AudioContext` tourne réellement (`running`) ; sinon, après une seconde, on renonce et le son reste direct
 *    (téléviseur ou navigateur qui exige un geste de l'utilisateur).
 *  - Un seul graphe par élément, un seul `AudioContext` pour la page.
 */
const RUNNING_WAIT_MS = 1000;

interface Attached {
  chain: SoundChain;
}

const attached = new WeakMap<HTMLMediaElement, Attached>();
const gaveUp = new WeakSet<HTMLMediaElement>();
let sharedContext: AudioContext | null = null;

function context(): AudioContext | null {
  if (sharedContext && sharedContext.state !== "closed") return sharedContext;
  const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  try {
    sharedContext = new Ctor({ latencyHint: "playback" });
  } catch {
    sharedContext = null;
  }
  return sharedContext;
}

async function attach(element: HTMLMediaElement, sound: RadioSoundSettings): Promise<void> {
  if (attached.has(element) || gaveUp.has(element)) return;
  const ctx = context();
  if (!ctx) {
    gaveUp.add(element);
    return;
  }
  if (ctx.state !== "running") {
    const resumed = ctx.resume().catch(() => undefined);
    await Promise.race([resumed, new Promise((resolve) => window.setTimeout(resolve, RUNNING_WAIT_MS))]);
  }
  if (ctx.state !== "running") {
    gaveUp.add(element);
    return;
  }
  if (attached.has(element)) return;
  try {
    const source = ctx.createMediaElementSource(element);
    const chain = createSoundChain(ctx, ctx.destination, sound);
    source.connect(chain.input);
    attached.set(element, { chain });
  } catch {
    gaveUp.add(element);
  }
}

export function useMediaSound(ref: RefObject<HTMLMediaElement | null>, rawSound: RadioSoundSettings | undefined): void {
  // Le serveur renvoie un objet neuf à chaque diffusion d'état : on ne réagit qu'à un changement de valeur.
  const key = rawSound ? JSON.stringify(rawSound) : "";
  useEffect(() => {
    const element = ref.current;
    if (!element || !key) return;
    const sound = JSON.parse(key) as RadioSoundSettings;
    const existing = attached.get(element);
    if (existing) {
      existing.chain.apply(sound, true);
      return;
    }
    if (isNeutralSound(sound)) return;
    const onPlaying = () => {
      void attach(element, sound);
    };
    if (!element.paused) onPlaying();
    element.addEventListener("playing", onPlaying);
    return () => element.removeEventListener("playing", onPlaying);
  }, [ref, key]);
}
