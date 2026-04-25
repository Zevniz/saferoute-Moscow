const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function resolveApiUrl(path) {
  if (!API_BASE_URL) {
    return path;
  }
  return `${API_BASE_URL}${path}`;
}

async function requestJson(path, options = {}) {
  const response = await fetch(resolveApiUrl(path), options);
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(payload?.detail ?? "SafeRoute API временно недоступен");
  }

  return payload;
}

export function searchPlaces(query, limit = 5, options = {}) {
  return requestJson(`/api/search?q=${encodeURIComponent(query)}&limit=${limit}`, options).then((payload) =>
    Array.isArray(payload) ? payload : [],
  );
}

export function fetchRoutes({ origin, destination, profile, mode, alternatives = 3 }, options = {}) {
  const params = new URLSearchParams({
    lat1: String(origin.lat),
    lon1: String(origin.lon),
    lat2: String(destination.lat),
    lon2: String(destination.lon),
    profile,
    alternatives: String(alternatives),
  });
  if (mode) {
    params.set("mode", mode);
  }
  return requestJson(`/api/route?${params.toString()}`, options);
}

export function fetchHealth(options = {}) {
  return requestJson("/api/health", options);
}

export function fetchSidewalkCells(bbox, resolution = 9, options = {}) {
  return requestJson(`/api/sidewalk-cells?bbox=${encodeURIComponent(bbox)}&resolution=${resolution}`, options);
}
