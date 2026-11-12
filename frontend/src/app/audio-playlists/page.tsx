"use client";

import { useEffect } from "react";

export default function AudioPlaylistsRedirectPage() {
  useEffect(() => {
    window.location.replace("/audio/");
  }, []);
  return null;
}
