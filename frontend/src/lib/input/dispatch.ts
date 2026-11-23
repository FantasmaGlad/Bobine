import { REMOTE_ACTIONS, type RemoteActionHandlers } from "../remoteBindings.ts";

export interface RemoteHandlers {
  onLeft?: () => void;
  onRight?: () => void;
  onUp?: () => void;
  onDown?: () => void;
  onEnter?: () => void;
  onBack?: () => void;
  onPlayPause?: () => void;
  onNext?: () => void;
  onPrev?: () => void;
  onChapterNext?: () => void;
  onChapterPrev?: () => void;
  onVolumeUp?: () => void;
  onVolumeDown?: () => void;
  onMute?: () => void;
}

function handlerName(action: string): keyof RemoteHandlers {
  return `on${action.split("_").map((part) => part[0].toUpperCase() + part.slice(1)).join("")}` as keyof RemoteHandlers;
}

export function actionHandlers(h: RemoteHandlers): RemoteActionHandlers {
  return Object.fromEntries(
    REMOTE_ACTIONS.map((action) => [action, h[handlerName(action)]]),
  );
}
