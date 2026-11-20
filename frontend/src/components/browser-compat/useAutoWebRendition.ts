import { useEffect, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";

export function useAutoWebRendition() {
  const [autoGenerate, setAutoGenerate] = useState(false);

  useEffect(() => {
    fetch(getApiUrl("/settings"), { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setAutoGenerate(data?.auto_web_rendition === "true"))
      .catch(() => {});
  }, []);

  const toggleAutoGenerate = async (checked: boolean) => {
    setAutoGenerate(checked);
    try {
      const res = await fetch(getApiUrl("/settings"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ auto_web_rendition: checked ? "true" : "false" }),
      });
      if (!res.ok) setAutoGenerate(!checked);
    } catch {
      setAutoGenerate(!checked);
    }
  };

  return { autoGenerate, toggleAutoGenerate };
}
