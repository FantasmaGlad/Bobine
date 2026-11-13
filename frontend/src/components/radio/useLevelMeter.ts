import { useEffect, type RefObject } from "react";
import type { MixStage } from "@/lib/radioMixGraph";

export function useLevelMeter(
  mixStageRef: RefObject<MixStage | null>,
  graphReady: boolean,
  metering: boolean,
  isPrimary: boolean,
  sendCommand: (command: string, params?: Record<string, unknown>) => void,
) {
  useEffect(() => {
    const stage = mixStageRef.current;
    if (!graphReady || !stage || !metering || !isPrimary) return;
    stage.setMetering(true);
    const id = setInterval(() => {
      const levels = stage.readLevels();
      if (Object.keys(levels).length) sendCommand("radio_report_levels", { levels });
    }, 250);
    return () => {
      clearInterval(id);
      stage.setMetering(false);
    };
  }, [mixStageRef, graphReady, metering, isPrimary, sendCommand]);
}
