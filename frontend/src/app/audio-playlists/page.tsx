"use client";

import { useEffect } from "react";

export default function AudioPlaylistsRedirectPage() {
  useEffect(() => {
    window.location.replace("/library/coach/?vue=playlists");
  }, []);
  return null;
}
