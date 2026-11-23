import { nextIndex, planSlot, type SignageEntry } from "../../../lib/signageLoop.ts";
import type { Slide } from "./slide.ts";

export const RETRY_MS = 5000;

export interface Stage {
  show(slide: Slide): void;
  clear(): void;
}

export type Prepare = (entry: SignageEntry, loop: boolean) => Promise<Slide | null>;

interface Pending {
  index: number;
  slide: Promise<Slide | null>;
}

export class SignageEngine {
  private entries: SignageEntry[] = [];
  private index = -1;
  private generation = 0;
  private failures = 0;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private pending: Pending | null = null;

  private readonly stage: Stage;
  private readonly prepareSlide: Prepare;

  constructor(stage: Stage, prepareSlide: Prepare) {
    this.stage = stage;
    this.prepareSlide = prepareSlide;
  }

  load(entries: SignageEntry[]) {
    this.reset();
    this.entries = entries;
    if (entries.length === 0) {
      this.stage.clear();
      return;
    }
    void this.advance();
  }

  stop() {
    this.reset();
    this.stage.clear();
  }

  private reset() {
    this.generation += 1;
    clearTimeout(this.timer);
    this.discardPending();
    this.index = -1;
    this.failures = 0;
  }

  private discardPending() {
    void this.pending?.slide.then((slide) => slide?.dispose());
    this.pending = null;
  }

  private prepare(index: number): Promise<Slide | null> {
    const entry = this.entries[index];
    return this.prepareSlide(entry, planSlot(entry, this.entries.length === 1).loop);
  }

  private take(index: number): Promise<Slide | null> {
    const pending = this.pending;
    this.pending = null;
    if (pending?.index === index) return pending.slide;
    void pending?.slide.then((slide) => slide?.dispose());
    return this.prepare(index);
  }

  private async advance() {
    const generation = this.generation;
    const target = nextIndex(this.index, this.entries.length);
    const slide = await this.take(target);
    if (generation !== this.generation) {
      slide?.dispose();
      return;
    }
    this.index = target;
    if (!slide) {
      this.skip();
      return;
    }
    this.failures = 0;
    this.present(target, slide);
  }

  private skip() {
    this.failures += 1;
    const delay = this.failures >= this.entries.length ? RETRY_MS : 0;
    if (delay) this.failures = 0;
    this.timer = setTimeout(() => void this.advance(), delay);
  }

  private present(index: number, slide: Slide) {
    const plan = planSlot(this.entries[index], this.entries.length === 1);
    this.stage.show(slide);
    slide.start();
    if (!plan.advances) return;
    const generation = this.generation;
    const next = () => {
      if (generation === this.generation) void this.advance();
    };
    if (plan.holdMs === null) slide.onEnded(next);
    else this.timer = setTimeout(next, plan.holdMs);
    const following = nextIndex(index, this.entries.length);
    this.pending = { index: following, slide: this.prepare(following) };
  }
}
