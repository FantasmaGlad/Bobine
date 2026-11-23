import type { Stage } from "./engine";
import type { Slide } from "./slide";

export const CROSSFADE_MS = 200;
const FRONT = "is-front";

export class Compositor implements Stage {
  private active = 0;
  private front: Slide | null = null;

  constructor(private readonly layers: readonly [HTMLElement, HTMLElement]) {}

  show(slide: Slide) {
    const incoming = this.layers[1 - this.active];
    incoming.replaceChildren(slide.element);
    incoming.classList.add(FRONT);
    this.layers[this.active].classList.remove(FRONT);
    this.active = 1 - this.active;
    const previous = this.front;
    this.front = slide;
    if (previous) window.setTimeout(() => previous.dispose(), CROSSFADE_MS);
  }

  clear() {
    this.front?.dispose();
    this.front = null;
    for (const layer of this.layers) {
      layer.replaceChildren();
      layer.classList.remove(FRONT);
    }
  }
}
