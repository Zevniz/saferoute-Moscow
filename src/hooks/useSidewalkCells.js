import { startTransition, useEffect, useState } from "react";

import { fetchSidewalkCells } from "../api/client";

export function useSidewalkCells({ enabled, mapRef }) {
  const [cells, setCells] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      setError("");
      setCells(null);
      return undefined;
    }

    const controller = new AbortController();
    const bounds = mapRef.current?.getBounds?.();
    const bbox = bounds
      ? [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()].join(",")
      : "37.50,55.68,37.75,55.82";

    async function load() {
      setLoading(true);
      setError("");
      try {
        const payload = await fetchSidewalkCells(bbox, 9, { signal: controller.signal });
        startTransition(() => setCells(payload));
      } catch (nextError) {
        if (nextError.name !== "AbortError") {
          startTransition(() => {
            setCells(null);
            setError(nextError.message || "Не удалось загрузить H3-ячейки");
          });
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    load();
    return () => controller.abort();
  }, [enabled, mapRef]);

  return { cells, loading, error };
}
