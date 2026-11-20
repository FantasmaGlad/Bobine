import { getApiUrl } from "@/lib/apiUrl";

type T = (key: string, params?: Record<string, string | number>) => string;

function hiddenVideo(): HTMLVideoElement {
  const element = document.createElement("video");
  element.muted = true;
  element.playsInline = true;
  element.preload = "auto";
  element.style.cssText = "position:fixed;width:1px;height:1px;opacity:0;pointer-events:none";
  document.body.appendChild(element);
  return element;
}

export async function runPlaybackProbe(t: T): Promise<string> {
  let element: HTMLVideoElement | null = null;
  try {
    const res = await fetch(getApiUrl("/videos?limit=1&sort_by=imported_at"), { cache: "no-store" });
    const videos = res.ok ? await res.json() : [];
    if (!videos.length) return t("browserCompat.testNoVideo");
    const { videoStreamUrl } = await import("@/lib/clientCodecSupport");
    element = hiddenVideo();
    element.src = videoStreamUrl(getApiUrl, videos[0].id);
    await element.play();
    await new Promise((resolve) => setTimeout(resolve, 5000));
    const quality = element.getVideoPlaybackQuality?.();
    return t("browserCompat.testResult", {
      dropped: quality?.droppedVideoFrames ?? 0,
      total: quality?.totalVideoFrames ?? 0,
      video: `${element.videoWidth}x${element.videoHeight}`,
    });
  } catch (err) {
    return t("browserCompat.testError", { reason: (err as Error).name || "erreur" });
  } finally {
    element?.remove();
  }
}
