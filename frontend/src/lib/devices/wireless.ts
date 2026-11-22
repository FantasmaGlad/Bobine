import type { BluetoothDevice } from "./types.ts";

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
