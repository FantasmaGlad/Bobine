export function unloadMedia(el: HTMLMediaElement | null | undefined): void {
  if (!el || (!el.src && !el.getAttribute("src"))) return;
  el.pause();
  el.removeAttribute("src");
  el.load();
}
