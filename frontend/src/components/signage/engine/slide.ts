export interface Slide {
  readonly element: HTMLElement;
  start(): void;
  onEnded(listener: () => void): void;
  dispose(): void;
}

export const PREPARE_TIMEOUT_MS = 15000;
