"use client";

import { useEffect } from "react";
import { dashboardHref } from "@/lib/navLinks";
import { DEFAULT_OUTPUT } from "@/lib/outputs";

export default function RootRedirect() {
  useEffect(() => {
    window.location.replace(`${dashboardHref(DEFAULT_OUTPUT)}/`);
  }, []);
  return null;
}
