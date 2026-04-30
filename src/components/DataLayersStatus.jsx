import { CloudSun, Info, ShieldCheck } from "lucide-react";

import { cn } from "../lib/ui";

export const INACTIVE_ADVANCED_LAYERS = [
  "бордюры",
  "зоны СИМ",
  "измеренный трафик",
  "плотность пешеходов",
  "телеметрия",
];

const ACTIVE_LAYER_LABELS = {
  surface_type: "покрытие",
  surface_quality: "качество покрытия",
  sidewalk_presence: "тротуары",
  lighting_quality: "освещение OSM",
  slope_percent: "уклон OSM",
  crossing_count: "переходы",
  controlled_crossing_count: "регулируемые переходы",
  uncontrolled_crossing_count: "нерегулируемые переходы",
  crossing_risk: "риск переходов",
};

const ACTIVE_LAYER_ORDER = [
  "surface_type",
  "surface_quality",
  "sidewalk_presence",
  "lighting_quality",
  "slope_percent",
  "crossing_count",
  "crossing_risk",
];

export function activeLayerLabels(enrichment) {
  const factors = Array.isArray(enrichment?.active_factors) ? enrichment.active_factors : [];
  return ACTIVE_LAYER_ORDER.filter((factor) => factors.includes(factor)).map((factor) => ACTIVE_LAYER_LABELS[factor]);
}

export function DataLayerPills({ score, compact = false, hideSourceSummary = false }) {
  const enrichment = score?.data_sources?.enrichment;
  const weather = score?.data_sources?.weather;
  const labels = enrichment?.active ? activeLayerLabels(enrichment) : [];
  const activeFactors = Array.isArray(enrichment?.active_factors) ? enrichment.active_factors : [];
  const hasCrossings = activeFactors.some((factor) => factor.includes("crossing"));

  return (
    <div className={cn("flex flex-wrap gap-2", compact ? "gap-1.5" : "")} data-testid="data-layer-badges">
      {labels.length && !hideSourceSummary ? (
        <span className="data-pill data-pill-active">
          <ShieldCheck size={13} aria-hidden="true" />
          <span>Данные OSM</span>
        </span>
      ) : !labels.length ? (
        <span className="data-pill data-pill-muted">
          <Info size={13} aria-hidden="true" />
          <span>Расширенные слои недоступны</span>
        </span>
      ) : null}
      {hasCrossings ? (
        <span className="data-pill data-pill-active">
          <span>Переходы</span>
        </span>
      ) : null}
      {labels.slice(0, compact ? 1 : 3).map((label) => (
        <span key={label} className="data-pill data-pill-soft">
          {label}
        </span>
      ))}
      {weather?.active ? (
        <span className="data-pill data-pill-weather">
          <CloudSun size={13} aria-hidden="true" />
          <span>Open-Meteo</span>
        </span>
      ) : null}
    </div>
  );
}

export function DataCoverageNote({ score }) {
  const enrichment = score?.data_sources?.enrichment;
  const labels = activeLayerLabels(enrichment);

  return (
    <section className="data-coverage-panel" aria-label="Статус слоёв безопасности">
      <div className="flex items-start gap-3">
        <div className="data-coverage-icon">
          <ShieldCheck size={17} aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-black tracking-tight text-on-surface">Покрытие данных</div>
          <p className="mt-1 text-xs font-medium leading-5 text-on-surface-variant">
            {labels.length
              ? `Активны реальные слои: ${labels.slice(0, 5).join(", ")}.`
            : "Расширенные слои пока не активны для этого маршрута."}
          </p>
          <p className="mt-2 text-xs font-medium leading-5 text-outline">
            Недоступны без проверенного источника: {INACTIVE_ADVANCED_LAYERS.join(", ")}.
          </p>
        </div>
      </div>
    </section>
  );
}
