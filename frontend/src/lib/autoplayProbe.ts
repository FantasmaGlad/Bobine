/**
 * Sonde d'autoplay audio, par DÉTECTION DE FONCTIONNALITÉ (jamais `navigator.userAgent`) :
 * un `AudioContext` tout juste créé passe à l'état « running » sans geste de l'utilisateur
 * uniquement si le navigateur autorise la lecture automatique.
 *
 * Pourquoi : le poste radio réclamait toujours un clic (« Démarrer la radio ») pour armer
 * l'audio, ce qui est impossible sur une sortie câblée (kiosque du Wyse, `Presentation` HDMI
 * Android, fenêtre projecteur) — où personne ne peut cliquer. Ces sorties lancent leur
 * navigateur avec l'autoplay autorisé (`--autoplay-policy=no-user-gesture-required`,
 * `mediaPlaybackRequiresUserGesture = false`, `with_autoplay(true)`) : la sonde le constate et
 * l'overlay n'apparaît pas. Un navigateur ordinaire reste « suspended » : l'overlay demeure.
 */
export function detectAutoplayAllowed(timeoutMs = 600): Promise<boolean> {
  return new Promise((resolve) => {
    if (typeof window === "undefined") {
      resolve(false);
      return;
    }
    const AudioContextClass =
      window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextClass) {
      resolve(false);
      return;
    }
    let ctx: AudioContext;
    try {
      ctx = new AudioContextClass();
    } catch {
      resolve(false);
      return;
    }
    let done = false;
    const finish = (allowed: boolean) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      ctx.removeEventListener("statechange", onStateChange);
      // La sonde est jetable : certains navigateurs limitent le nombre de contextes ouverts.
      ctx.close().catch(() => {});
      resolve(allowed);
    };
    const onStateChange = () => {
      if (ctx.state === "running") finish(true);
    };
    // `finish` et `onStateChange` ne sont appelés qu'après cette initialisation.
    const timer = setTimeout(() => finish(ctx.state === "running"), timeoutMs);
    ctx.addEventListener("statechange", onStateChange);
    if (ctx.state === "running") {
      finish(true);
      return;
    }
    // Bloqué : cette promesse reste en attente (ou échoue) tant qu'aucun geste n'a eu lieu.
    ctx.resume().then(onStateChange).catch(() => {});
  });
}
