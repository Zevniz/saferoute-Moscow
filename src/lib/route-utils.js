const PROFILE_SPEEDS = {
  walk: 4.8,
  bike: 14,
  car: 28,
};

const VARIANT_LABELS = {
  safe: "Наиболее безопасный",
  balanced: "Сбалансированный",
  fast: "Самый быстрый",
};

const VARIANT_SUBTITLES = {
  walk: {
    safe: "Меньше рискованных участков для пешего пути",
    balanced: "Ровный баланс темпа и спокойствия",
    fast: "Минимальное время в пути пешком",
  },
  bike: {
    safe: "Приоритет спокойным улицам",
    balanced: "Баланс темпа и безопасности на дороге",
    fast: "Быстрее добраться на велосипеде",
  },
  car: {
    safe: "Через более спокойные улицы",
    balanced: "Баланс скорости и дорожного комфорта",
    fast: "Минимальное время за рулем",
  },
};

const DEFAULT_VARIANT_BY_PROFILE = {
  walk: ["safe", "balanced", "fast"],
  bike: ["balanced", "safe", "fast"],
  car: ["fast", "balanced", "safe"],
};

const EPSILON = 1e-7;
const SHORT_MANEUVER_METERS = 120;
const SHORT_MANEUVER_SECONDS = 120;

const DIRECTION_PHRASES = {
  "север": "на север",
  "юг": "на юг",
  "восток": "на восток",
  "запад": "на запад",
  "северо-восток": "на северо-восток",
  "северо-запад": "на северо-запад",
  "юго-восток": "на юго-восток",
  "юго-запад": "на юго-запад",
};

const ROUTE_DIRECTIONS_PATTERN =
  "(северо-восток|северо-запад|юго-восток|юго-запад|север|юг|восток|запад)";
const ROUTE_DIRECTION_TAIL_PATTERN = "(\\s+.*|[.,!?].*|$)";

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function duplicateStartPoint(lines) {
  if (!lines.length || !lines[0].length) {
    return [0, 0];
  }

  return [...lines[0][0]];
}

function normalizeVariant(variant, index) {
  if (variant === "safe" || variant === "balanced" || variant === "fast") {
    return variant;
  }

  return ["safe", "balanced", "fast"][index] ?? "safe";
}

function normalizeRouteLabel(label, variant) {
  if (!label || /valhalla/i.test(String(label))) {
    return VARIANT_LABELS[variant];
  }

  return label;
}

function pointDistance(start, end) {
  const dx = end[0] - start[0];
  const dy = end[1] - start[1];
  return Math.sqrt(dx * dx + dy * dy);
}

function estimateMinutes(distanceMeters, profile) {
  const speed = PROFILE_SPEEDS[profile] ?? PROFILE_SPEEDS.walk;
  return Math.max(1, Math.round((distanceMeters / 1000 / speed) * 60));
}

function estimateCalories(distanceMeters, profile) {
  if (profile === "walk") {
    return Math.max(0, Math.round(distanceMeters * 0.05));
  }

  if (profile === "bike") {
    return Math.max(0, Math.round(distanceMeters * 0.03));
  }

  return 0;
}

function normalizeSafetyIndex(value) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.round(clamp(value, 0, 100));
  }

  return 95;
}

function normalizeInstructionText(value) {
  const rawText = String(value ?? "").trim().replace(/[‐‑‒–—]/g, "-");
  if (!rawText) {
    return "Манёвр маршрута";
  }

  const withLevel = rawText.replace(/\bLevel\s*(-?\d+)\b/gi, "уровень $1");
  const stairsMatch = withLevel.match(/^Воспользуйтесь лестниц(?:ей|ами) до уровень\s*(-?\d+)\.?$/i);
  if (stairsMatch) {
    const level = Number(stairsMatch[1]);
    return level < 0
      ? `Спуститесь по лестнице на уровень ${stairsMatch[1]}.`
      : `Поднимитесь по лестнице на уровень ${stairsMatch[1]}.`;
  }

  const directionMatch = withLevel.match(new RegExp(`^Идите\\s+${ROUTE_DIRECTIONS_PATTERN}${ROUTE_DIRECTION_TAIL_PATTERN}`, "i"));
  if (directionMatch) {
    const direction = DIRECTION_PHRASES[directionMatch[1].toLowerCase()] ?? directionMatch[1].toLowerCase();
    return `Двигайтесь ${direction}${directionMatch[2]}`;
  }

  const normalized = withLevel
    .replace(/^Идите\s+на\s+/i, "Двигайтесь на ")
    .replace(/^Идите\s+по\b/i, "Двигайтесь по")
    .replace(/^Идите\s+/i, "Двигайтесь ")
    .replace(/^Идите\b/i, "Двигайтесь");

  return normalized.replace(new RegExp(`^Двигайтесь\\s+${ROUTE_DIRECTIONS_PATTERN}${ROUTE_DIRECTION_TAIL_PATTERN}`, "i"), (_, rawDirection, rest) => {
    const direction = DIRECTION_PHRASES[rawDirection.toLowerCase()] ?? rawDirection.toLowerCase();
    return `Двигайтесь ${direction}${rest}`;
  });
}

function normalizeInstructions(value) {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.map((instruction, index) => ({
    index: Number.isFinite(Number(instruction?.index)) ? Number(instruction.index) : index,
    text: normalizeInstructionText(instruction?.text || instruction?.instruction),
    distance_m: Number(instruction?.distance_m ?? instruction?.distance ?? 0) || 0,
    time_s: Number(instruction?.time_s ?? instruction?.time ?? 0) || 0,
    begin_shape_index: Number(instruction?.begin_shape_index ?? 0) || 0,
    end_shape_index: Number(instruction?.end_shape_index ?? instruction?.begin_shape_index ?? 0) || 0,
    type: instruction?.type ?? "continue",
    street_names: Array.isArray(instruction?.street_names) ? instruction.street_names : [],
    lanes: Array.isArray(instruction?.lanes) ? instruction.lanes : [],
  }));
}

function parseGeometry(rawGeometry) {
  if (!rawGeometry) {
    return null;
  }

  let geometry = rawGeometry;
  if (typeof rawGeometry === "string") {
    try {
      geometry = JSON.parse(rawGeometry);
    } catch {
      return null;
    }
  } else if (rawGeometry.type === "Feature") {
    geometry = rawGeometry.geometry;
  }

  if (!geometry?.type || !Array.isArray(geometry.coordinates)) {
    return null;
  }

  if (geometry.type === "LineString") {
    return geometry.coordinates.length >= 2 ? geometry : null;
  }

  if (geometry.type === "MultiLineString") {
    return geometry.coordinates.length > 0 ? geometry : null;
  }

  return null;
}

function orientGeometry(geometry, origin, destination) {
  if (!geometry || !origin || !destination) {
    return geometry;
  }

  const lines = getGeometryLines(geometry);
  if (!lines.length || !lines[0].length) {
    return geometry;
  }

  const firstPoint = lines[0][0];
  const lastLine = lines[lines.length - 1];
  const lastPoint = lastLine[lastLine.length - 1];

  const originPoint = [origin.lon, origin.lat];
  const destinationPoint = [destination.lon, destination.lat];
  const startAlignment = pointDistance(firstPoint, originPoint) + pointDistance(lastPoint, destinationPoint);
  const reverseAlignment = pointDistance(firstPoint, destinationPoint) + pointDistance(lastPoint, originPoint);

  if (startAlignment <= reverseAlignment) {
    return geometry;
  }

  const reversedLines = [...lines]
    .reverse()
    .map((line) => [...line].reverse());

  if (geometry.type === "LineString") {
    return { type: "LineString", coordinates: reversedLines[0] };
  }

  return { type: "MultiLineString", coordinates: reversedLines };
}

function normalizeRoute(route, index, profile, origin, destination) {
  const variant = normalizeVariant(route?.properties?.variant ?? route?.variant, index);
  const routeProfile = route?.properties?.profile ?? profile;
  const parsedGeometry = parseGeometry(route?.geometry ?? route);
  if (!parsedGeometry) {
    return null;
  }
  const geometry = orientGeometry(parsedGeometry, origin, destination);

  const rawDistance = Number(route?.properties?.distance_m ?? route?.distance_m ?? 0);
  const distanceMeters = Number.isFinite(rawDistance) ? rawDistance : 0;
  const rawMinutes = Number(
    route?.properties?.estimated_mins ?? route?.estimated_mins ?? estimateMinutes(distanceMeters, profile),
  );
  const estimatedMins = Number.isFinite(rawMinutes) ? rawMinutes : estimateMinutes(distanceMeters, profile);
  const rawCalories = Number(
    route?.properties?.calories_burn ?? route?.calories_burn ?? estimateCalories(distanceMeters, profile),
  );
  const calories = Number.isFinite(rawCalories) ? rawCalories : estimateCalories(distanceMeters, profile);

  return {
    id: route?.id ?? `${profile}-${variant}-${index}`,
    label: normalizeRouteLabel(route?.label, variant),
    subtitle: route?.subtitle ?? VARIANT_SUBTITLES[profile]?.[variant] ?? "Подходящий вариант маршрута",
    type: "Feature",
    properties: {
      distance_m: distanceMeters,
      estimated_mins: estimatedMins,
      safety_index: normalizeSafetyIndex(route?.properties?.safety_index ?? route?.safety_index),
      calories_burn: routeProfile === "car" ? 0 : calories,
      profile: routeProfile,
      variant,
      mode: route?.properties?.mode ?? route?.mode ?? "safest",
      instructions: normalizeInstructions(route?.properties?.instructions ?? route?.instructions),
      bbox: route?.properties?.bbox ?? route?.bbox ?? null,
      source: route?.properties?.source ?? route?.source ?? "unknown",
      score: route?.properties?.score ?? route?.score ?? null,
    },
    geometry,
  };
}

export function normalizeRoutePayload(payload, { profile, origin, destination }) {
  if (Array.isArray(payload?.routes)) {
    const routes = payload.routes
      .map((route, index) => normalizeRoute(route, index, profile, origin, destination))
      .filter(Boolean);

    return {
      routes,
      meta: {
        profile: payload?.meta?.profile ?? profile,
        origin: payload?.meta?.origin ?? origin,
        destination: payload?.meta?.destination ?? destination,
      },
    };
  }

  if (payload?.geometry) {
    const legacyRoute = normalizeRoute(
      {
        id: `${profile}-safe-legacy`,
        label: VARIANT_LABELS.safe,
        subtitle: VARIANT_SUBTITLES[profile]?.safe ?? "Базовый маршрут",
        properties: {
          distance_m: Number(payload?.meters ?? 0),
          estimated_mins: estimateMinutes(Number(payload?.meters ?? 0), profile),
          safety_index: typeof payload?.score === "number" ? normalizeSafetyIndex(100 - payload.score / 100) : 95,
          calories_burn: estimateCalories(Number(payload?.meters ?? 0), profile),
          profile,
          variant: "safe",
        },
        geometry: payload.geometry,
      },
      0,
      profile,
      origin,
      destination,
    );

    return {
      routes: legacyRoute ? [legacyRoute] : [],
      meta: { profile, origin, destination },
    };
  }

  return { routes: [], meta: { profile, origin, destination } };
}

function getGeometryLines(geometry) {
  if (!geometry) {
    return [];
  }

  return geometry.type === "LineString" ? [geometry.coordinates] : geometry.coordinates;
}

function segmentLength(start, end) {
  const dx = end[0] - start[0];
  const dy = end[1] - start[1];
  return Math.sqrt(dx * dx + dy * dy);
}

function buildLineLength(line) {
  let length = 0;
  for (let index = 1; index < line.length; index += 1) {
    length += segmentLength(line[index - 1], line[index]);
  }
  return length;
}

function buildPartialLine(line, remainingLength) {
  if (line.length < 2) {
    return [line[0] ?? [0, 0], line[0] ?? [0, 0]];
  }

  const partial = [line[0]];
  let consumed = 0;

  for (let index = 1; index < line.length; index += 1) {
    const start = line[index - 1];
    const end = line[index];
    const currentSegmentLength = segmentLength(start, end);

    if (consumed + currentSegmentLength <= remainingLength + EPSILON) {
      partial.push(end);
      consumed += currentSegmentLength;
      continue;
    }

    const available = Math.max(0, remainingLength - consumed);
    const ratio = currentSegmentLength > 0 ? available / currentSegmentLength : 0;
    const interpolated = [
      start[0] + (end[0] - start[0]) * ratio,
      start[1] + (end[1] - start[1]) * ratio,
    ];
    partial.push(interpolated);
    return partial.length >= 2 ? partial : [line[0], interpolated];
  }

  return partial;
}

export function getProgressiveGeometry(geometry, progress) {
  if (!geometry) {
    return null;
  }

  if (progress >= 1) {
    return geometry;
  }

  const lines = getGeometryLines(geometry);
  if (!lines.length) {
    return geometry;
  }

  const totalLength = lines.reduce((sum, line) => sum + buildLineLength(line), 0);
  if (totalLength <= EPSILON) {
    return geometry;
  }

  let remainingLength = totalLength * clamp(progress, 0, 1);
  const partialLines = [];

  for (const line of lines) {
    const lineLength = buildLineLength(line);
    if (remainingLength <= EPSILON) {
      break;
    }

    if (remainingLength >= lineLength) {
      partialLines.push(line);
      remainingLength -= lineLength;
      continue;
    }

    partialLines.push(buildPartialLine(line, remainingLength));
    remainingLength = 0;
    break;
  }

  if (!partialLines.length) {
    const duplicated = duplicateStartPoint(lines);
    return geometry.type === "LineString"
      ? { type: "LineString", coordinates: [duplicated, duplicated] }
      : { type: "MultiLineString", coordinates: [[[...duplicated], [...duplicated]]] };
  }

  if (geometry.type === "LineString") {
    return { type: "LineString", coordinates: partialLines[0] };
  }

  return { type: "MultiLineString", coordinates: partialLines };
}

export function getGeometryBounds(geometry) {
  const lines = getGeometryLines(geometry);
  if (!lines.length) {
    return null;
  }

  let minLon = Infinity;
  let minLat = Infinity;
  let maxLon = -Infinity;
  let maxLat = -Infinity;

  lines.forEach((line) => {
    line.forEach(([lon, lat]) => {
      minLon = Math.min(minLon, lon);
      minLat = Math.min(minLat, lat);
      maxLon = Math.max(maxLon, lon);
      maxLat = Math.max(maxLat, lat);
    });
  });

  return [
    [minLon, minLat],
    [maxLon, maxLat],
  ];
}

export function flattenGeometryCoordinates(geometry) {
  return getGeometryLines(geometry).flat();
}

function toRadians(value) {
  return (value * Math.PI) / 180;
}

export function distanceInMeters(start, end) {
  const earthRadius = 6371000;
  const dLat = toRadians(end[1] - start[1]);
  const dLon = toRadians(end[0] - start[0]);
  const lat1 = toRadians(start[1]);
  const lat2 = toRadians(end[1]);

  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) * Math.sin(dLon / 2);

  return 2 * earthRadius * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function bearing(start, end) {
  const startLat = toRadians(start[1]);
  const startLon = toRadians(start[0]);
  const endLat = toRadians(end[1]);
  const endLon = toRadians(end[0]);

  const y = Math.sin(endLon - startLon) * Math.cos(endLat);
  const x =
    Math.cos(startLat) * Math.sin(endLat) -
    Math.sin(startLat) * Math.cos(endLat) * Math.cos(endLon - startLon);

  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

function normalizeBearingDelta(value) {
  if (value > 180) {
    return value - 360;
  }

  if (value < -180) {
    return value + 360;
  }

  return value;
}

function formatTurnDistance(distanceMeters) {
  if (distanceMeters < 80) {
    return "Сейчас";
  }

  if (distanceMeters < 1000) {
    return `Через ${Math.round(distanceMeters / 10) * 10} м`;
  }

  return `Через ${(distanceMeters / 1000).toFixed(1)} км`;
}

export function getNavigationHint(route) {
  const coordinates = flattenGeometryCoordinates(route?.geometry);
  if (coordinates.length < 3) {
    return {
      title: "Маршрут рассчитан",
      subtitle: "Маршрут уже рассчитан",
    };
  }

  let travelled = 0;

  for (let index = 1; index < coordinates.length - 1; index += 1) {
    const previous = coordinates[index - 1];
    const current = coordinates[index];
    const next = coordinates[index + 1];

    travelled += distanceInMeters(previous, current);
    const firstBearing = bearing(previous, current);
    const secondBearing = bearing(current, next);
    const delta = normalizeBearingDelta(secondBearing - firstBearing);
    const absoluteDelta = Math.abs(delta);

    if (absoluteDelta < 18) {
      continue;
    }

    if (absoluteDelta >= 55) {
      return {
        title: `Поверните ${delta > 0 ? "направо" : "налево"}`,
        subtitle: formatTurnDistance(travelled),
      };
    }

    return {
      title: `Плавно поверните ${delta > 0 ? "направо" : "налево"}`,
      subtitle: formatTurnDistance(travelled),
    };
  }

  return {
    title: "Следуйте прямо",
    subtitle: "Продолжайте движение по маршруту",
  };
}

function projectPointToSegment(point, start, end) {
  const referenceLat = toRadians((point[1] + start[1] + end[1]) / 3);
  const metersPerDegreeLat = 111_320;
  const metersPerDegreeLon = Math.max(1, metersPerDegreeLat * Math.cos(referenceLat));

  const px = (point[0] - start[0]) * metersPerDegreeLon;
  const py = (point[1] - start[1]) * metersPerDegreeLat;
  const sx = 0;
  const sy = 0;
  const ex = (end[0] - start[0]) * metersPerDegreeLon;
  const ey = (end[1] - start[1]) * metersPerDegreeLat;
  const dx = ex - sx;
  const dy = ey - sy;
  const segmentLengthSquared = dx * dx + dy * dy;
  const ratio = segmentLengthSquared > 0 ? clamp((px * dx + py * dy) / segmentLengthSquared, 0, 1) : 0;
  const projectedX = sx + dx * ratio;
  const projectedY = sy + dy * ratio;
  const distance = Math.hypot(px - projectedX, py - projectedY);

  return { distance, ratio };
}

export function getRouteProgressForPosition(geometry, position) {
  const coordinates = flattenGeometryCoordinates(geometry);
  if (!position || coordinates.length < 2) {
    return {
      nearestShapeIndex: 0,
      distanceToRouteMeters: Infinity,
      progress: 0,
    };
  }

  const point = [position.lon, position.lat];
  const segmentLengths = [];
  let totalLength = 0;
  for (let index = 1; index < coordinates.length; index += 1) {
    const length = distanceInMeters(coordinates[index - 1], coordinates[index]);
    segmentLengths.push(length);
    totalLength += length;
  }

  let best = {
    distanceToRouteMeters: Infinity,
    nearestShapeIndex: 0,
    progressMeters: 0,
  };
  let consumed = 0;

  for (let index = 1; index < coordinates.length; index += 1) {
    const projection = projectPointToSegment(point, coordinates[index - 1], coordinates[index]);
    const progressMeters = consumed + segmentLengths[index - 1] * projection.ratio;
    if (projection.distance < best.distanceToRouteMeters) {
      best = {
        distanceToRouteMeters: projection.distance,
        nearestShapeIndex: projection.ratio > 0.62 ? index : index - 1,
        progressMeters,
      };
    }
    consumed += segmentLengths[index - 1];
  }

  return {
    nearestShapeIndex: best.nearestShapeIndex,
    distanceToRouteMeters: best.distanceToRouteMeters,
    progress: totalLength > 0 ? clamp(best.progressMeters / totalLength, 0, 1) : 0,
  };
}

export function getInstructionIndexForShape(instructions, shapeIndex) {
  if (!Array.isArray(instructions) || instructions.length === 0) {
    return 0;
  }

  const match = instructions.find((instruction) => {
    const begin = Number(instruction.begin_shape_index ?? 0);
    const end = Number(instruction.end_shape_index ?? begin);
    return shapeIndex >= begin && shapeIndex <= end;
  });

  if (match) {
    return instructions.indexOf(match);
  }

  const next = instructions.find((instruction) => Number(instruction.begin_shape_index ?? 0) > shapeIndex);
  if (next) {
    return Math.max(0, instructions.indexOf(next) - 1);
  }

  return Math.max(0, instructions.length - 1);
}

export function getInstructionPresentation(instruction, nextInstruction) {
  if (!instruction) {
    return {
      title: "Ожидаем следующий манёвр",
      subtitle: "Ожидаем GPS-позицию",
    };
  }

  const distance = formatInstructionMeta(instruction);
  const street = instruction.street_names?.[0];
  const nextText = nextInstruction?.text ? `Далее: ${nextInstruction.text}` : "До финиша";

  return {
    title: instruction.text,
    subtitle: street ? `${distance} • ${street}` : `${distance} • ${nextText}`,
  };
}

export function formatDistance(distanceMeters) {
  if (!distanceMeters) {
    return "--";
  }

  if (distanceMeters < 1000) {
    return `${Math.round(distanceMeters)} м`;
  }

  return `${(distanceMeters / 1000).toFixed(1)} км`;
}

export function formatInstructionMeta(instruction) {
  const meters = Number(instruction?.distance_m ?? 0);
  const distance = formatDistance(instruction?.distance_m);
  const seconds = Number(instruction?.time_s ?? 0);
  if (meters > 0 && meters < 25) {
    return "Сейчас";
  }

  if (!seconds || seconds < SHORT_MANEUVER_SECONDS || meters < SHORT_MANEUVER_METERS) {
    return distance;
  }

  const minutes = Math.max(1, Math.round(seconds / 60));
  return `${distance} • ${minutes} мин`;
}

export function formatCalories(calories) {
  if (!calories) {
    return null;
  }

  return `${Math.round(calories)} kcal`;
}

export function getDefaultRouteId(routes, profile) {
  const preferredVariants = DEFAULT_VARIANT_BY_PROFILE[profile] ?? DEFAULT_VARIANT_BY_PROFILE.walk;

  for (const variant of preferredVariants) {
    const match = routes.find((route) => route?.properties?.variant === variant);
    if (match) {
      return match.id;
    }
  }

  return routes[0]?.id ?? null;
}

export function getArrivalTime(estimatedMinutes) {
  const arrivalDate = new Date(Date.now() + estimatedMinutes * 60_000);
  return new Intl.DateTimeFormat("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(arrivalDate);
}
