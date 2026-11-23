"use client";

import type { DragEvent } from "react";

import PageNav from "@/components/PageNav";
import ImportVisualsButton from "@/components/visuals/ImportVisualsButton";
import { useVisualLibrary } from "@/components/visuals/useVisualLibrary";
import VisualsLibrary from "@/components/visuals/VisualsLibrary";
import { useAppSettings } from "@/lib/AppSettingsContext";
import { useToast } from "@/lib/useToast";

export default function VisualsLibraryPage() {
  const { t } = useAppSettings();
  const { toast, showToast } = useToast();
  const visuals = useVisualLibrary();
  const drop = (e: DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files?.length) visuals.importFiles(Array.from(e.dataTransfer.files));
  };

  return (
    <div className="library-container playlists-mode" onDragOver={(e) => e.preventDefault()} onDrop={drop}>
      <PageNav
        tabs={[{ id: "visuals", icon: "slideshow", label: t("library.visualsTab") }]}
        value="visuals"
        onChange={() => {}}
        ariaLabel={t("library.visualsTab")}
        actions={<ImportVisualsButton label={t("common.import")} onFiles={visuals.importFiles} />}
      />
      {toast && <div className={`toast ${toast.type}`}><span>{toast.message}</span></div>}
      <VisualsLibrary visuals={visuals.visuals} failed={visuals.failed} onRename={visuals.rename} onRemove={visuals.remove} showToast={showToast} />
    </div>
  );
}
