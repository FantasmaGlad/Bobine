import { useCallback, useEffect, useState } from "react";
import { getApiUrl } from "@/lib/apiUrl";
import { copyText } from "@/lib/clipboard";
import { reportAsText, type ImportDiagnostics } from "@/lib/importDiagnostics";

export function useImportDiagnostics() {
  const [report, setReport] = useState<ImportDiagnostics | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [copied, setCopied] = useState(false);

  const fetchReport = useCallback(() => fetch(getApiUrl("/diagnostics/import"), { cache: "no-store" })
    .then(async (res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setReport(await res.json());
      setFailed(false);
    })
    .catch(() => setFailed(true))
    .finally(() => setLoading(false)), []);

  const load = () => {
    setLoading(true);
    void fetchReport();
  };

  useEffect(() => {
    void fetchReport();
  }, [fetchReport]);

  const copy = async () => {
    if (!report) return;
    if (await copyText(reportAsText(report))) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  return { report, loading, failed, copied, load, copy };
}
