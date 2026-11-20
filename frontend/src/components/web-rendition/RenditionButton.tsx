import Icon from "@/components/Icon";
import { type VideoWebState } from "./useWebRendition";

type T = (key: string, params?: Record<string, string | number>) => string;

export default function RenditionButton({ status, busy, act, t }: { status: VideoWebState["web_status"]; busy: boolean; act: (method: "POST" | "DELETE") => void; t: T }) {
  if (status === "ready") {
    return (
      <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={() => act("DELETE")}>
        {t("webRendition.remove")}
      </button>
    );
  }
  return (
    <button type="button" className="btn btn-primary btn-sm" disabled={busy || status === "pending"} onClick={() => act("POST")}>
      {status === "pending" ? (
        <>
          <Icon name="sync" size={14} className="olc-spin" /> {t("webRendition.creating")}
        </>
      ) : (
        t("webRendition.create")
      )}
    </button>
  );
}
