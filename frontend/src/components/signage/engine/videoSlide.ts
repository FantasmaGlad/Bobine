import { PREPARE_TIMEOUT_MS, type Slide } from "./slide";

function release(video: HTMLVideoElement) {
  video.pause();
  video.remove();
  video.removeAttribute("src");
  video.load();
}

function playable(video: HTMLVideoElement): Promise<boolean> {
  if (video.readyState >= HTMLMediaElement.HAVE_FUTURE_DATA) return Promise.resolve(true);
  return new Promise((resolve) => {
    const settle = (ok: boolean) => {
      window.clearTimeout(timer);
      video.removeEventListener("canplay", onReady);
      video.removeEventListener("error", onError);
      resolve(ok);
    };
    const onReady = () => settle(true);
    const onError = () => settle(false);
    const timer = window.setTimeout(() => settle(false), PREPARE_TIMEOUT_MS);
    video.addEventListener("canplay", onReady);
    video.addEventListener("error", onError);
  });
}

export async function prepareVideo(src: string, title: string, loop: boolean): Promise<Slide | null> {
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;
  video.loop = loop;
  video.preload = "auto";
  video.disablePictureInPicture = true;
  video.disableRemotePlayback = true;
  video.src = src;
  if (!(await playable(video))) {
    console.warn("Visuel vidéo illisible", title, video.error?.code ?? "délai dépassé");
    release(video);
    return null;
  }
  return {
    element: video,
    start: () => {
      video.play().catch((error) => console.warn("Lecture du visuel refusée", title, error));
    },
    onEnded: (listener) => video.addEventListener("ended", listener, { once: true }),
    dispose: () => release(video),
  };
}
