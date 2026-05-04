/**
 * Crossing visualization utilities for SafeRoute
 */

/**
 * Get icon/emoji for crossing type
 */
export function getCrossingIcon(type) {
  const icons = {
    traffic_signal: '🚦',
    marked: '🚶',
    unmarked: '⚠️',
    underpass: '⬇️',
    overpass: '⬆️',
    unknown: '❓'
  };
  return icons[type] || icons.unknown;
}

/**
 * Get human-readable label for crossing type
 */
export function getCrossingLabel(type) {
  const labels = {
    traffic_signal: 'Переход со светофором',
    marked: 'Размеченный переход (зебра)',
    unmarked: 'Нерегулируемый переход',
    underpass: 'Подземный переход',
    overpass: 'Надземный переход',
    unknown: 'Переход (тип неизвестен)'
  };
  return labels[type] || labels.unknown;
}

/**
 * Get color for crossing type
 */
export function getCrossingColor(type) {
  const colors = {
    traffic_signal: '#22c55e', // green
    marked: '#3b82f6', // blue
    unmarked: '#f59e0b', // amber
    underpass: '#8b5cf6', // purple
    overpass: '#8b5cf6', // purple
    unknown: '#6b7280' // gray
  };
  return colors[type] || colors.unknown;
}

/**
 * Format crossing summary for display
 */
export function formatCrossingSummary(summary) {
  if (!summary || summary.total === 0) {
    return 'Переходов не обнаружено';
  }

  const parts = [];
  
  if (summary.traffic_signals > 0) {
    parts.push(`${summary.traffic_signals} со светофором`);
  }
  if (summary.marked > 0) {
    parts.push(`${summary.marked} зебра`);
  }
  if (summary.unmarked > 0) {
    parts.push(`${summary.unmarked} нерегулируемых`);
  }
  if (summary.underpass > 0) {
    parts.push(`${summary.underpass} подземных`);
  }
  if (summary.overpass > 0) {
    parts.push(`${summary.overpass} надземных`);
  }

  return `Переходы: ${summary.total} всего · ${parts.join(' · ')}`;
}

/**
 * Get safety description based on crossing summary
 */
export function getCrossingSafetyDescription(summary) {
  if (!summary || summary.total === 0) {
    return null;
  }

  const controlled = summary.traffic_signals + summary.underpass + summary.overpass;
  const total = summary.total;
  const controlledPercent = (controlled / total) * 100;

  if (controlledPercent >= 80) {
    return 'Большинство переходов регулируемые или безопасные';
  } else if (controlledPercent >= 50) {
    return 'Часть переходов регулируемые';
  } else if (summary.unmarked > 0) {
    return 'Есть нерегулируемые переходы — будьте внимательны';
  } else {
    return 'Переходы в основном размеченные';
  }
}
