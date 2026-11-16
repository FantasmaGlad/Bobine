import type { Dict } from "../core.ts";

export const chapters: Dict = {
  title: "Chapters",
  toastLabel: "Chapter",
  import: "Import (.json, .vtt, .txt)",
  fromFile: "Read from video",
  export: "Export",
  addHere: "Add here",
  save: "Save chapters",
  saved: "Chapters saved",
  empty: "No chapters. Import a file or add them from the player.",
  titlePlaceholder: "Chapter title",
  remove: "Remove this chapter",
  importHint: "JSON format: { \"chapters\": [ { \"start\": \"05:00\", \"title\": \"Cardio\" } ] } — or a \"05:00 Title\" list, or a WebVTT file.",
  error: "Chapters not saved",
};
