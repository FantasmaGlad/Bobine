import { activateDomFocus, moveDomFocus2D, selectRemoteTarget } from "@/lib/useKioskRemote";
import { VOLUME_STEP } from "@/lib/volumeHud";

export const CINEMA_GRID_CARDS = ".cinema-grid-layer .cinema-hero-play, .cinema-grid-layer .cinema-card, .cinema-grid-layer .cinema-all-item";

export interface RemoteContext {
  phase: "grid" | "playing" | "ended";
  standby: boolean;
  setStandby: (on: boolean) => void;
  volume: (delta: number, mute?: boolean) => void;
  playPause: () => void;
  back: () => void;
  seekBy: (delta: number) => void;
  chapter: (direction: "next" | "prev") => void;
  playNext: () => void;
}

function focusHero() {
  document.querySelector<HTMLElement>(".cinema-grid-layer")?.scrollTo({ top: 0, behavior: "smooth" });
  const items = Array.from(document.querySelectorAll<HTMLElement>(CINEMA_GRID_CARDS));
  const hero = items.find((el) => el.classList.contains("cinema-hero-play"));
  if (hero) selectRemoteTarget(items, hero);
}

function gridKeys(ctx: RemoteContext) {
  if (ctx.standby) {
    const exit = () => {
      ctx.setStandby(false);
      setTimeout(focusHero, 50);
    };
    return { onEnter: exit, onPlayPause: exit, onLeft: exit, onRight: exit, onUp: exit, onDown: exit, onBack: exit };
  }
  const move = (direction: "left" | "right" | "up" | "down") => () => moveDomFocus2D(CINEMA_GRID_CARDS, direction);
  return {
    onLeft: move("left"), onRight: move("right"), onUp: move("up"), onDown: move("down"), onPrev: move("left"), onNext: move("right"),
    onEnter: () => activateDomFocus(CINEMA_GRID_CARDS),
    onPlayPause: () => activateDomFocus(CINEMA_GRID_CARDS),
    onBack: () => {
      if ((document.querySelector<HTMLElement>(".cinema-grid-layer")?.scrollTop ?? 0) > 0) focusHero();
      else ctx.setStandby(true);
    },
  };
}

export function cinemaRemoteKeys(ctx: RemoteContext) {
  const volume = {
    onVolumeUp: () => ctx.volume(VOLUME_STEP),
    onVolumeDown: () => ctx.volume(-VOLUME_STEP),
    onMute: () => ctx.volume(0, true),
  };
  if (ctx.phase === "grid") return { ...volume, ...gridKeys(ctx) };
  if (ctx.phase === "ended") return { ...volume, onEnter: ctx.playNext, onPlayPause: ctx.playNext, onBack: ctx.back };
  return {
    ...volume,
    onEnter: ctx.playPause, onPlayPause: ctx.playPause, onBack: ctx.back,
    onLeft: () => ctx.seekBy(-10), onRight: () => ctx.seekBy(10),
    onUp: volume.onVolumeUp, onDown: volume.onVolumeDown,
    onPrev: () => ctx.seekBy(-30), onNext: () => ctx.seekBy(30),
    onChapterNext: () => ctx.chapter("next"), onChapterPrev: () => ctx.chapter("prev"),
  };
}
