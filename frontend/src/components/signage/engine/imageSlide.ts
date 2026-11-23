import type { Slide } from "./slide";

export async function prepareImage(src: string, title: string): Promise<Slide | null> {
  const image = new Image();
  image.decoding = "async";
  image.alt = title;
  image.src = src;
  try {
    await image.decode();
  } catch (error) {
    console.warn("Visuel image illisible", title, error);
    image.removeAttribute("src");
    return null;
  }
  return {
    element: image,
    start: () => undefined,
    onEnded: () => undefined,
    dispose: () => {
      image.remove();
      image.removeAttribute("src");
    },
  };
}
