"use client";

import { useEffect, useState } from "react";
import { nfseApi, type HealthResponse } from "@/app/lib/nfse-api";

export function HealthBanner() {
  const [h, setH] = useState<HealthResponse | null>(null);

  useEffect(() => {
    nfseApi.health().then(setH).catch(() => setH({ enabled: false }));
  }, []);

  if (!h || !h.enabled) return null;
  const last = h.last_job;
  if (!last) return null;

  const stale = last.finalizado_em
    ? Date.now() - new Date(last.finalizado_em).getTime() > 36 * 3600 * 1000
    : true;
  const ok = last.status === "ok" && !stale;
  if (ok) return null;

  return (
    <div className="mb-4 rounded-lg border border-danger bg-danger/[0.08] p-3 text-sm text-danger">
      <strong>NFS-e sync:</strong>{" "}
      {last.status !== "ok"
        ? `último job falhou (${last.status})`
        : "sem sync há mais de 36h"}
      {last.iniciado_em && ` — ${new Date(last.iniciado_em).toLocaleString("pt-BR")}`}
    </div>
  );
}
