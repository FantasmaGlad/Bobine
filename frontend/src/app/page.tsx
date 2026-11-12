"use client";

import { useEffect } from "react";

export default function RootRedirect() {
  useEffect(() => {
    window.location.replace("/dashboard-cable/");
  }, []);
  return null;
}
