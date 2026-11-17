import type { BluetoothDevice, WifiNetwork, WifiPendingChange } from "./types.ts";

export function signalBars(signal: number): number {
  if (signal >= 75) return 4;
  if (signal >= 50) return 3;
  if (signal >= 25) return 2;
  return signal > 0 ? 1 : 0;
}

export type WifiConnectPlan = "direct" | "needs_password" | "password_local_only";

export function wifiConnectPlan(network: Pick<WifiNetwork, "known" | "security">, local: boolean): WifiConnectPlan {
  if (network.known || !network.security) return "direct";
  return local ? "needs_password" : "password_local_only";
}

export function splitBluetooth(devices: BluetoothDevice[]): { paired: BluetoothDevice[]; nearby: BluetoothDevice[] } {
  const byName = (a: BluetoothDevice, b: BluetoothDevice) => Number(b.connected) - Number(a.connected) || a.name.localeCompare(b.name);
  return {
    paired: devices.filter((d) => d.paired).sort(byName),
    nearby: devices.filter((d) => !d.paired).sort((a, b) => (b.rssi ?? -200) - (a.rssi ?? -200) || a.name.localeCompare(b.name)),
  };
}

export function bluetoothKindIcon(kind: string): string {
  switch (kind) {
    case "headphones": return "headphones";
    case "headset": return "headset_mic";
    case "speaker": return "speaker";
    case "keyboard": return "keyboard";
    case "mouse": return "mouse";
    case "gamepad": return "sports_esports";
    case "phone": return "smartphone";
    case "computer": return "computer";
    default: return "bluetooth";
  }
}

export function secondsLeft(pending: WifiPendingChange | null | undefined, elapsedSeconds: number): number {
  if (!pending) return 0;
  return Math.max(0, pending.seconds_left - Math.floor(elapsedSeconds));
}
