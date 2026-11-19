"use client";

import Icon from "@/components/Icon";
import MarkdownView from "@/components/MarkdownView";

export default function ReleaseNotesToggle({ notes, label, showReleaseNotes, setShowReleaseNotes }: {
  notes: string; label: string; showReleaseNotes: boolean; setShowReleaseNotes: (update: (v: boolean) => boolean) => void;
}) {
  return (
    <div>
      <button
        type="button"
        className="btn btn-secondary btn-sm"
        style={{ marginBottom: "8px" }}
        onClick={() => setShowReleaseNotes((v) => !v)}
      >
        <Icon name={showReleaseNotes ? "expand_less" : "expand_more"} size={16} />
        {label}
      </button>
      {showReleaseNotes && (
        <div className="update-notes-box olc-anim-in">
          <MarkdownView content={notes} />
        </div>
      )}
    </div>
  );
}
