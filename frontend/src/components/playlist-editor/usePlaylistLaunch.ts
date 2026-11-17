import { usePlaybackSocket } from "@/lib/usePlaybackSocket";
import type { ShowToast } from "@/lib/useToast";
import type { Translate } from "./types";

export function usePlaylistLaunch(prefix: string, t: Translate, showToast: ShowToast, command: string, param: string) {
  const { connected, sendCommand } = usePlaybackSocket();
  return (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    if (!connected) {
      showToast(t(`${prefix}.screenDisconnected`), "error");
      return;
    }
    sendCommand(command, { [param]: id });
    showToast(t(`${prefix}.launchedToast`));
  };
}
