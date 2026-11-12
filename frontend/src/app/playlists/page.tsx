"use client";

import { useEffect } from "react";

export default function PlaylistsRedirectPage() {
  useEffect(() => {
    window.location.replace("/library/");
  }, []);
  return null;
}
