import { useCallback, useRef, useState } from "react";

import { searchPlaces } from "../api/client";

export function useSearch() {
  const activeRequestsRef = useRef(0);
  const [loading, setLoading] = useState(false);

  const search = useCallback(async (query, limit = 5, options = {}) => {
    activeRequestsRef.current += 1;
    setLoading(true);
    try {
      return await searchPlaces(query, limit, options);
    } finally {
      activeRequestsRef.current = Math.max(0, activeRequestsRef.current - 1);
      setLoading(activeRequestsRef.current > 0);
    }
  }, []);

  return { loading, search };
}
