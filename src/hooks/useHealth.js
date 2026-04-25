import { useCallback, useState } from "react";

import { fetchHealth } from "../api/client";

export function useHealth() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadHealth = useCallback(async () => {
    setLoading(true);
    try {
      const payload = await fetchHealth();
      setHealth(payload);
    } catch (error) {
      setHealth({
        status: "degraded",
        services: {
          postgres: { status: "unknown", detail: "not checked" },
          photon: { status: "unknown", detail: "not checked" },
          valhalla: { status: "unknown", detail: error.message || "offline" },
        },
      });
    } finally {
      setLoading(false);
    }
  }, []);

  return { health, loading, loadHealth };
}
