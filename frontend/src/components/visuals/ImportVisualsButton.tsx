"use client";

import { useRef } from "react";
import Icon from "@/components/Icon";
import { ARCHIVE_ACCEPT, BACKGROUND_ACCEPT } from "@/lib/mediaFiles";

export default function ImportVisualsButton({ label, onFiles, className = "btn btn-primary" }: { label: string; onFiles: (files: File[]) => void; className?: string }) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <input ref={input} type="file" multiple accept={`${BACKGROUND_ACCEPT},${ARCHIVE_ACCEPT}`} hidden
        onChange={(e) => { if (e.target.files?.length) onFiles(Array.from(e.target.files)); e.target.value = ""; }} />
      <button type="button" className={className} onClick={() => input.current?.click()}>
        <Icon name="cloud_upload" size={18} />
        <span>{label}</span>
      </button>
    </>
  );
}
