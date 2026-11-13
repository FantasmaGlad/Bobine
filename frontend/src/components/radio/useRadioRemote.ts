import { useKioskRemote } from "@/lib/useKioskRemote";

interface RadioRemoteOptions {
  unlocked: boolean;
  hasTrack: boolean;
  volume: number;
  handleUnlock: () => void;
  handlePlayPause: () => void;
  sendCommand: (command: string, params?: Record<string, unknown>) => void;
}

export function useRadioRemote({ unlocked, hasTrack, volume, handleUnlock, handlePlayPause, sendCommand }: RadioRemoteOptions) {
  const changeRadioVolume = (delta: number) => {
    sendCommand("volume", { volume: Math.max(0, Math.min(100, volume + delta)) });
  };
  useKioskRemote(() => {
    if (!unlocked) {
      return { onEnter: handleUnlock, onPlayPause: handleUnlock };
    }
    if (!hasTrack) return {};
    return {
      onPlayPause: handlePlayPause,
      onEnter: handlePlayPause,
      onRight: () => sendCommand("radio_next_track"),
      onNext: () => sendCommand("radio_next_track"),
      onLeft: () => sendCommand("radio_previous_track"),
      onPrev: () => sendCommand("radio_previous_track"),
      onUp: () => changeRadioVolume(5),
      onVolumeUp: () => changeRadioVolume(5),
      onDown: () => changeRadioVolume(-5),
      onVolumeDown: () => changeRadioVolume(-5),
      onMute: () => sendCommand("volume", { volume: 0 }),
    };
  });
}
