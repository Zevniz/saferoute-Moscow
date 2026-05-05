/**
 * Route snapping visualization utilities for SafeRoute
 */

export function getSnappingWarningLevel(distanceMeters) {
  if (!distanceMeters || distanceMeters <= 30) {
    return 'none';
  }
  if (distanceMeters <= 80) {
    return 'soft';
  }
  return 'warning';
}

export function formatSnappingMessage(distanceMeters, endpoint = 'finish') {
  const level = getSnappingWarningLevel(distanceMeters);
  const pointLabel = endpoint === 'start' ? 'старта' : 'финиша';

  if (level === 'soft') {
    return `${pointLabel === 'старта' ? 'Старт' : 'Финиш'} привязан к ближайшему доступному пешеходному пути.`;
  }

  const rounded = Math.round(distanceMeters);
  return `Маршрут ${pointLabel === 'старта' ? 'начинается' : 'заканчивается'} примерно в ${rounded} м от выбранной точки: рядом нет доступного пешеходного пути в данных карты.`;
}

export function formatSnappingMessageShort(distanceMeters, endpoint = 'finish') {
  const rounded = Math.round(distanceMeters);
  const pointLabel = endpoint === 'start' ? 'старта' : 'финиша';
  
  return `От ${pointLabel}: ~${rounded} м вне доступного пешеходного графа`;
}

export function getSnappedMarkerTooltip(endpoint, distanceMeters) {
  const rounded = Math.round(distanceMeters);
  const pointLabel = endpoint === 'start' ? 'начинается' : 'заканчивается';
  
  return `Маршрут ${pointLabel} здесь. Выбранная точка находится примерно в ${rounded} м.`;
}

export function getRawMarkerTooltip(endpoint) {
  return endpoint === 'start' ? 'Выбранный старт' : 'Выбранный финиш';
}

export function analyzeRouteSnapping(debug) {
  if (!debug) {
    return {
      hasStartSnapping: false,
      hasFinishSnapping: false,
      startDistance: null,
      finishDistance: null,
      startLevel: 'none',
      finishLevel: 'none',
    };
  }

  const startDistance = debug.start_snap_distance_m;
  const finishDistance = debug.finish_snap_distance_m;

  return {
    hasStartSnapping: startDistance > 30,
    hasFinishSnapping: finishDistance > 30,
    startDistance,
    finishDistance,
    startLevel: getSnappingWarningLevel(startDistance),
    finishLevel: getSnappingWarningLevel(finishDistance),
  };
}
