export function cn(...values) {
  return values.filter(Boolean).join(" ");
}

export function getViewportPadding(stage) {
  const isCompact = typeof window !== "undefined" ? window.innerWidth < 768 : false;
  if (stage === "navigating") {
    return isCompact
      ? { top: 138, bottom: 196, left: 24, right: 24 }
      : { top: 152, bottom: 164, left: 84, right: 84 };
  }

  return isCompact
    ? { top: 118, bottom: 96, left: 24, right: 24 }
    : { top: 110, bottom: 92, left: 368, right: 96 };
}

export function buildDestinationLabel(result, fallbackQuery) {
  return result?.label || fallbackQuery;
}
