import { useState, type RefObject } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import { isRadioAudioName } from "@/lib/mediaFiles";
import { useUploadManager } from "@/lib/UploadManager";
import type { ShowToast } from "@/lib/useToast";

type Translate = (key: string, vars?: Record<string, string | number>) => string;


function configurePicker(el: HTMLInputElement, folder: boolean) {
  if (folder) {
    el.setAttribute("webkitdirectory", "");
    el.setAttribute("directory", "");
  } else {
    el.removeAttribute("webkitdirectory");
    el.removeAttribute("directory");
  }
  el.multiple = folder;
  el.click();
}

const clearInput = (fileInputRef: RefObject<HTMLInputElement | null>) => {
  if (fileInputRef.current) fileInputRef.current.value = "";
};

function useFileUpload(fileInputRef: RefObject<HTMLInputElement | null>, t: Translate, showToast: ShowToast, fetchAll: () => void) {
  const [description, setDescription] = useState("");
  const [uploading, setUploading] = useState(false);
  const [selectedFileName, setSelectedFileName] = useState("");

  const uploadFile = async () => {
    const file = fileInputRef.current?.files?.[0];
    if (!file || !description.trim()) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("description", description.trim());
      const res = await fetch(getApiUrl("/radio/announcements/upload"), { method: "POST", body: fd });
      if (res.ok) {
        showToast(t("radioAnnouncements.importedToast"));
        setDescription("");
        setSelectedFileName("");
        clearInput(fileInputRef);
        fetchAll();
      } else {
        showToast(t("radioAnnouncements.importError"), "error");
      }
    } catch {
      showToast(t("radioAnnouncements.importError"), "error");
    } finally {
      setUploading(false);
    }
  };

  return { description, setDescription, uploading, selectedFileName, setSelectedFileName, uploadFile };
}

const dragHandler = (setDragActive: (active: boolean) => void) => (e: React.DragEvent) => {
  e.preventDefault();
  e.stopPropagation();
  setDragActive(e.type === "dragenter" || e.type === "dragover");
};

export function useAnnouncementImport(fileInputRef: RefObject<HTMLInputElement | null>, t: Translate, showToast: ShowToast, fetchAll: () => void) {
  const { addUploads } = useUploadManager();
  const upload = useFileUpload(fileInputRef, t, showToast, fetchAll);
  const { setSelectedFileName } = upload;
  const [uploadMode, setUploadMode] = useState<"file" | "folder">("file");
  const [dragActive, setDragActive] = useState(false);
  const handleDrag = dragHandler(setDragActive);
  const [showImportCard, setShowImportCard] = useState(false);

  const openPicker = (folder: boolean) => {
    setUploadMode(folder ? "folder" : "file");
    if (fileInputRef.current) configurePicker(fileInputRef.current, folder);
  };

  const uploadFolder = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    const files = Array.from(fileList).filter((f) => isRadioAudioName(f.name));
    if (files.length === 0) {
      showToast(t("radioAnnouncements.noAudioInFolder"), "warning");
      clearInput(fileInputRef);
      return;
    }
    addUploads(files.map((f) => ({ kind: "radio_announcement_files" as const, files: [f], title: f.name })));
    showToast(t("radioAnnouncements.importStarted"));
    clearInput(fileInputRef);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (uploadMode === "folder") {
      uploadFolder(e.dataTransfer.files);
    } else if (e.dataTransfer.files?.[0] && fileInputRef.current) {
      const dt = new DataTransfer();
      dt.items.add(e.dataTransfer.files[0]);
      fileInputRef.current.files = dt.files;
      setSelectedFileName(e.dataTransfer.files[0].name);
    }
  };

  const close = () => {
    setShowImportCard(false);
    setSelectedFileName("");
    clearInput(fileInputRef);
  };

  return {
    ...upload, uploadMode, dragActive, showImportCard, setShowImportCard, openPicker, uploadFolder, handleDrag, handleDrop, close,
  };
}

export type AnnouncementImport = ReturnType<typeof useAnnouncementImport>;
