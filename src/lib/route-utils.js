const PROFILE_SPEEDS = {
  walk: 4.8,
  bike: 14,
  car: 28,
};

const VARIANT_LABELS = {
  safe: "С более высокой оценкой",
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
    balanced: "Баланс темпа и дорожного комфорта",
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

const SCORE_REASON_COPY = {
  safety_weight: {
    label: "базовый граф",
    concern: "Основа маршрута",
    timeline: "Маршрут рассчитан по проверенному графу Москвы.",
    tone: "neutral",
  },
  walk_friendly_edges: {
    label: "больше пешеходных участков",
    concern: "Спокойствие",
    timeline: "Есть участки, более дружелюбные к пешему движению.",
    tone: "positive",
  },
  cycleway_edges: {
    label: "есть велоинфраструктура",
    concern: "Колёса",
    timeline: "Маршрут использует участки, подходящие для велосипеда или самоката.",
    tone: "positive",
  },
  high_speed_or_lanes: {
    label: "рядом более активная дорога",
    concern: "Дорожная среда",
    timeline: "По пути есть участки с большей дорожной экспозицией.",
    tone: "caution",
  },
  narrow_width: {
    label: "узкие участки",
    concern: "Комфорт",
    timeline: "По пути возможны более узкие отрезки.",
    tone: "caution",
  },
  narrow_sidewalk_width: {
    label: "узкий тротуар",
    concern: "Комфорт",
    timeline: "Есть участки, где тротуар может быть теснее.",
    tone: "caution",
  },
  wide_width: {
    label: "широкий участок",
    concern: "Комфорт",
    timeline: "Часть маршрута проходит по более широким участкам.",
    tone: "positive",
  },
  bad_surface: {
    label: "сложное покрытие",
    concern: "Покрытие",
    timeline: "OSM отмечает покрытие, которое может быть менее комфортным.",
    tone: "caution",
  },
  smooth_surface: {
    label: "ровное покрытие",
    concern: "Покрытие",
    timeline: "OSM отмечает ровное или асфальтовое покрытие на значимой части пути.",
    tone: "positive",
  },
  missing_sidewalk: {
    label: "не везде есть тротуар",
    concern: "Тротуары",
    timeline: "OSM отмечает участки без явного тротуара.",
    tone: "risk",
  },
  many_crossings: {
    label: "много переходов",
    concern: "Переходы",
    timeline: "По пути есть несколько переходов из активного OSM-слоя.",
    tone: "caution",
  },
  poor_lighting: {
    label: "слабое освещение",
    concern: "Освещение",
    timeline: "OSM lit-теги показывают участки с плохим или отсутствующим освещением.",
    tone: "caution",
  },
  good_lighting: {
    label: "лучше освещено",
    concern: "Освещение",
    timeline: "OSM lit-теги показывают хорошее освещение на значимой части пути.",
    tone: "positive",
  },
  steep_slope: {
    label: "заметный уклон",
    concern: "Уклон",
    timeline: "На маршруте есть уклон из OSM incline-данных.",
    tone: "caution",
  },
  low_traffic: {
    label: "спокойнее дорога",
    concern: "Дорожная среда",
    timeline: "Граф указывает на более спокойную дорожную среду.",
    tone: "positive",
  },
  road_exposure_proxy: {
    label: "дорожная экспозиция",
    concern: "Дорожная среда",
    timeline: "Это не измеренный трафик, а дорожная экспозиция из графа.",
    tone: "caution",
  },
  weather_sensitive_risk: {
    label: "погодный риск",
    concern: "Погода",
    timeline: "Open-Meteo вернул погодный риск для маршрута.",
    tone: "caution",
  },
  telemetry_confidence: {
    label: "реальные наблюдения",
    concern: "Покрытие данных",
    timeline: "Есть реальные агрегированные наблюдения для части маршрута.",
    tone: "positive",
  },
};

const INACTIVE_LAYER_COPY = [
  "бордюры",
  "официальные зоны СИМ",
  "измеренный трафик",
  "плотность пешеходов",
  "телеметрия",
];

const ACTIVE_FACTOR_LABELS = {
  surface_type: "тип покрытия",
  surface_quality: "качество покрытия",
  sidewalk_presence: "тротуары",
  lighting_quality: "освещение по OSM",
  slope_percent: "уклон по OSM",
  crossing_count: "переходы",
  controlled_crossing_count: "регулируемые переходы",
  uncontrolled_crossing_count: "нерегулируемые переходы",
  crossing_risk: "риск переходов",
};

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

function publicReasonCopy(reason) {
  return SCORE_REASON_COPY[reason?.code] ?? {
    label: reason?.code?.replaceAll("_", " ") ?? "фактор маршрута",
    concern: "Маршрут",
    timeline: "API вернул дополнительный фактор оценки.",
    tone: reason?.impact === "positive" ? "positive" : reason?.impact === "penalty" ? "caution" : "neutral",
  };
}

function visibleScoreReasons(score) {
  const reasons = Array.isArray(score?.reasons) ? score.reasons : [];
  return reasons.filter((reason) => reason?.code && reason.code !== "safety_weight");
}

export function getRouteConfidence(route) {
  const score = route?.properties?.score;
  if (!score) {
    return {
      value: null,
      label: "После расчёта",
      description: "Покрытие данных появится вместе с оценкой маршрута.",
      tone: "neutral",
      caveat: "Это не гарантия безопасности.",
    };
  }

  const factors = score.factors ?? {};
  const enrichment = score.data_sources?.enrichment;
  const weather = score.data_sources?.weather;
  const telemetry = score.data_sources?.telemetry;
  const activeFactors = Array.isArray(enrichment?.active_factors) ? enrichment.active_factors : [];
  const enrichmentConfidence = typeof factors.avg_enrichment_confidence === "number" ? factors.avg_enrichment_confidence : null;
  const telemetryConfidence = typeof factors.avg_telemetry_confidence === "number" ? factors.avg_telemetry_confidence : null;

  let value = 42;
  if (enrichment?.active) {
    value += 22;
  }
  value += Math.min(16, activeFactors.length * 2);
  if (activeFactors.some((factor) => factor.includes("crossing"))) {
    value += 7;
  }
  if (typeof enrichmentConfidence === "number") {
    value += Math.round(enrichmentConfidence * 12);
  }
  if (weather?.active) {
    value += 4;
  }
  if (telemetry?.active && typeof telemetryConfidence === "number") {
    value += Math.round(telemetryConfidence * 8);
  }

  const bounded = clamp(Math.round(value), 0, 96);
  const label = bounded >= 82 ? "Высокая" : bounded >= 64 ? "Средняя" : "Ограниченная";

  return {
    value: bounded,
    label,
    tone: bounded >= 82 ? "positive" : bounded >= 64 ? "neutral" : "caution",
    description:
      bounded >= 82
        ? "Оценку поддерживают активные OSM-слои и переходы."
        : "Оценка честно ограничена доступными слоями; отсутствующие данные не подменяются.",
    caveat: "Даже высокая уверенность данных не гарантирует безопасную обстановку на месте.",
  };
}

export function getRouteInsight(route, routes = []) {
  const score = route?.properties?.score;
  const reasons = visibleScoreReasons(score);
  const topReason = reasons[0] ? publicReasonCopy(reasons[0]) : null;
  const confidence = getRouteConfidence(route);
  const scoreTotal = typeof score?.total === "number" ? score.total : route?.properties?.safety_index ?? null;
  const otherRoutes = routes.filter((candidate) => candidate?.id !== route?.id);
  const safestScore = Math.max(...routes.map((candidate) => candidate?.properties?.score?.total ?? candidate?.properties?.safety_index ?? 0), 0);
  const fastestMinutes = Math.min(...routes.map((candidate) => candidate?.properties?.estimated_mins ?? Infinity));
  const selectedMinutes = route?.properties?.estimated_mins ?? null;
  const minuteDelta = Number.isFinite(fastestMinutes) && selectedMinutes ? selectedMinutes - fastestMinutes : 0;

  let comparison = "Сравнение появится, когда API вернёт несколько вариантов.";
  if (otherRoutes.length > 0 && scoreTotal === safestScore && minuteDelta > 1) {
    comparison = `Этот вариант спокойнее по оценке, но примерно на ${minuteDelta} мин дольше самого быстрого.`;
  } else if (otherRoutes.length > 0 && selectedMinutes === fastestMinutes && scoreTotal < safestScore) {
    comparison = "Это самый быстрый вариант, но его оценка ниже, чем у более спокойной альтернативы.";
  } else if (otherRoutes.length > 0 && scoreTotal === safestScore) {
    comparison = "Это один из вариантов с самой высокой оценкой среди найденных маршрутов.";
  } else if (otherRoutes.length > 0) {
    comparison = "Этот вариант балансирует время и спокойствие относительно остальных маршрутов.";
  }

  const reasonPhrase = reasons
    .slice(0, 2)
    .map((reason) => publicReasonCopy(reason).label)
    .join(" и ");

  return {
    confidence,
    topReasonLabel: topReason?.label ?? "оценка по реальным данным",
    comparison,
    brief: reasonPhrase
      ? `По доступным данным маршрут выглядит спокойнее: учтены ${reasonPhrase}.`
      : "Маршрут рассчитан по реальному графу; дополнительных факторов для краткого объяснения API не вернул.",
    limitation: "Оценка помогает сравнить варианты, но не является гарантией безопасности.",
    unavailable: INACTIVE_LAYER_COPY,
  };
}

export function getRouteKnowledge(route) {
  const score = route?.properties?.score;
  const enrichment = score?.data_sources?.enrichment;
  const weather = score?.data_sources?.weather;
  const activeFactors = Array.isArray(enrichment?.active_factors) ? enrichment.active_factors : [];
  const known = [];

  known.push("геометрия, время и расстояние реального маршрута");

  if (score) {
    known.push("оценка и причины, которые вернул API");
  }

  const activeLabels = activeFactors
    .map((factor) => ACTIVE_FACTOR_LABELS[factor])
    .filter(Boolean);

  if (enrichment?.active && activeLabels.length) {
    known.push(`активные OSM-слои: ${activeLabels.slice(0, 5).join(", ")}`);
  }

  if (activeFactors.some((factor) => factor.includes("crossing"))) {
    known.push("переходы из активного OSM-слоя");
  }

  if (weather?.active) {
    known.push("текущая погода от Open-Meteo для маршрута");
  }

  const instructions = route?.properties?.instructions ?? [];
  if (instructions.length) {
    known.push("первые манёвры и финишные подсказки маршрута");
  }

  return {
    known: [...new Set(known)].slice(0, 5),
    unknown: INACTIVE_LAYER_COPY.map((layer) => `${layer}: нет активного проверенного источника`),
    note: "Неизвестные риски не считаются безопасными и не добавляются в оценку.",
  };
}

export function getRouteTimeline(route) {
  const instructions = route?.properties?.instructions ?? [];
  const score = route?.properties?.score;
  const reasons = visibleScoreReasons(score);
  const timeline = [];

  if (instructions[0]) {
    timeline.push({
      id: "start",
      title: "Старт",
      description: instructions[0].text,
      meta: formatInstructionMeta(instructions[0]),
      tone: "neutral",
    });
  }

  reasons.slice(0, 4).forEach((reason, index) => {
    const copy = publicReasonCopy(reason);
    timeline.push({
      id: `${reason.code}-${index}`,
      title: copy.concern,
      description: copy.timeline,
      meta: reason.impact === "positive" ? "помогает оценке" : reason.impact === "penalty" ? "учтено в оценке" : "информация",
      tone: copy.tone,
    });
  });

  if (instructions.length > 1) {
    const finalInstruction = instructions[instructions.length - 1];
    timeline.push({
      id: "finish",
      title: "Финиш",
      description: finalInstruction.text,
      meta: formatInstructionMeta(finalInstruction),
      tone: "neutral",
    });
  }

  if (!timeline.length) {
    timeline.push({
      id: "empty",
      title: "Маршрут рассчитан",
      description: "Подробности появятся после расчёта реального маршрута.",
      meta: "без выдуманных факторов",
      tone: "neutral",
    });
  }

  return timeline;
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
