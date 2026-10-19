/**
 * Copie dans le presse-papiers, y compris sur une page servie en HTTP simple.
 *
 * Cause du défaut corrigé (« copier » dans Réglages ne copiait pas l'URL) : Bobine est surtout ouvert
 * par son adresse IP locale (`http://192.168.1.x:8000`), un contexte NON sécurisé où
 * `navigator.clipboard` n'existe pas. L'appel échouait en silence (un simple message à l'écran) et le
 * presse-papiers gardait son ancien contenu — par exemple l'adresse de la page d'administration
 * qu'on venait de copier dans la barre du navigateur. Repli : sélection d'un champ temporaire et
 * `document.execCommand("copy")`, que les navigateurs autorisent sur un geste de l'utilisateur.
 *
 * Renvoie vrai si la copie a réussi (l'appelant n'annonce « copié » que dans ce cas).
 */
export async function copyText(text: string): Promise<boolean> {
  if (typeof window !== "undefined" && window.isSecureContext && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // permission refusée ou document sans focus : on tente le repli ci-dessous
    }
  }
  return copyWithSelection(text);
}

function copyWithSelection(text: string): boolean {
  if (typeof document === "undefined" || !document.body) return false;
  const previouslyFocused = document.activeElement as HTMLElement | null;
  const field = document.createElement("textarea");
  field.value = text;
  // Hors écran mais sélectionnable (display:none empêcherait la sélection) ; lecture seule pour ne pas
  // ouvrir le clavier virtuel sur mobile.
  field.setAttribute("readonly", "");
  field.setAttribute("aria-hidden", "true");
  field.style.cssText = "position:fixed;top:0;left:-9999px;width:1px;height:1px;opacity:0;";
  document.body.appendChild(field);
  try {
    field.focus();
    field.select();
    field.setSelectionRange(0, text.length);
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    document.body.removeChild(field);
    previouslyFocused?.focus?.();
  }
}
