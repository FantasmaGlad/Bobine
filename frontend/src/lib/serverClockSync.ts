import { ClockOffsetEstimator } from "@/lib/playbackClock";

const BURST_DELAYS_MS = [0, 150, 300, 450, 600];
const REFRESH_INTERVAL_MS = 30000;

export class ServerClockSync {
  private readonly estimator = new ClockOffsetEstimator();
  private timers: ReturnType<typeof setTimeout>[] = [];
  private interval: ReturnType<typeof setInterval> | null = null;

  start(ws: WebSocket, isCurrent: () => boolean): void {
    this.stop();
    const send = () => {
      if (isCurrent() && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ command: "time_sync", params: { t0: Date.now() } }));
      }
    };
    this.timers = BURST_DELAYS_MS.map((delay) => setTimeout(send, delay));
    this.interval = setInterval(send, REFRESH_INTERVAL_MS);
  }

  stop(): void {
    this.timers.forEach(clearTimeout);
    this.timers = [];
    if (this.interval) clearInterval(this.interval);
    this.interval = null;
  }

  handleMessage(parsed: { event?: string; t0?: unknown; server_ms?: unknown }): boolean {
    if (parsed.event !== "time_sync") return false;
    if (typeof parsed.t0 === "number" && typeof parsed.server_ms === "number") {
      this.estimator.add(parsed.t0, parsed.server_ms, Date.now());
    }
    return true;
  }

  serverNow = (): number => Date.now() + this.estimator.offsetMs();
}
