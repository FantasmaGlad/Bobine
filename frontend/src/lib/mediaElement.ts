/**
 * Libère le flux et les tampons d'un élément média. Retirer `src` ne suffit pas : sans `load()`, le navigateur
 * garde le décodeur et les données déjà téléchargées jusqu'au ramasse-miettes.
 */
export function unloadMedia(el: HTMLMediaElement | null | undefined): void {
  if (!el || (!el.src && !el.getAttribute("src"))) return;
  el.pause();
  el.removeAttribute("src");
  el.load();
}
