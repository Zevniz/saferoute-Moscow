import { useCallback, useRef, useState } from "react";

import { fetchRoutes } from "../api/client";

export function useRoutes() {
  const activeRequestsRef = useRef(0);
  const [loading, setLoading] = useState(false);

  const loadRoutes = useCallback(async (request, options = {}) => {
    activeRequestsRef.current += 1;
    setLoading(true);
    try {
      return await fetchRoutes(request, options);
    } finally {
      activeRequestsRef.current = Math.max(0, activeRequestsRef.current - 1);
      setLoading(activeRequestsRef.current > 0);
    }
  }, []);

  return { loading, loadRoutes };
}
