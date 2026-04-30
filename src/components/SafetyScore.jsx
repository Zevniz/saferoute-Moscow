import { motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Info, ShieldCheck } from "lucide-react";

import { OVERLAY_TRANSITION } from "../config/safeRoute";
import { DataLayerPills } from "./DataLayersStatus";

const REASON_LABELS = {
  safety_weight: "Базовый граф безопасности",
  walk_friendly_edges: "Пешеходные участки",
  cycleway_edges: "Велополоса",
  high_speed_or_lanes: "Дорожная экспозиция",
  narrow_width: "Узкий участок",
  narrow_sidewalk_width: "Узкий тротуар",
  medium_width: "Средняя ширина",
  wide_width: "Широкий участок",
  bad_surface: "Покрытие",
  smooth_surface: "Ровное покрытие",
  missing_sidewalk: "Нет тротуара",
  curb_risk: "Бордюры",
  many_crossings: "Переходы",
  poor_lighting: "Освещение",
  steep_slope: "Уклон",
  low_traffic: "Низкая дорожная экспозиция",
  traffic_intensity: "Измеренный трафик",
  road_exposure_proxy: "Дорожная экспозиция",
  micromobility_forbidden: "Запрет СИМ",
  forbidden_zone: "Запретная зона",
  micromobility_slow_zone: "Зона ограничения",
  telemetry_confidence: "Телеметрия",
  good_lighting: "Хорошее освещение",
  weather_sensitive_risk: "Погода",
};

function scoreTone(total) {
  if (typeof total !== "number") {
    return { label: "Данных мало", className: "score-ring-muted", Icon: Info };
  }
  if (total >= 85) {
    return { label: "Отлично", className: "score-ring-excellent", Icon: CheckCircle2 };
  }
  if (total >= 70) {
    return { label: "Хорошо", className: "score-ring-good", Icon: ShieldCheck };
  }
  return { label: "Осторожно", className: "score-ring-caution", Icon: AlertTriangle };
}

function reasonLabel(reason) {
  return REASON_LABELS[reason?.code] ?? reason?.code?.replaceAll("_", " ") ?? "Фактор";
}

function topReasons(score, limit = 3) {
  const reasons = Array.isArray(score?.reasons) ? score.reasons : [];
  return reasons.filter((reason) => reason?.code && reason.code !== "safety_weight").slice(0, limit);
}

export function SafetyScorePanel({ route }) {
  const score = route?.properties?.score;
  const total = score?.total;
  const tone = scoreTone(total);
  const Icon = tone.Icon;
  const reasons = topReasons(score);

  if (!route) {
    return null;
  }

  return (
    <motion.section
      initial={{ opacity: 0, y: 8, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={OVERLAY_TRANSITION}
      className="safety-score-panel"
      aria-label="Разбор оценки безопасности"
    >
      <div className="flex items-start gap-4">
        <div className={`score-ring ${tone.className}`}>
          <span className="score-ring-number">{typeof total === "number" ? total : "--"}</span>
          <span className="score-ring-unit">/100</span>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-sm font-black text-on-surface">
            <Icon size={16} aria-hidden="true" />
            {tone.label}
          </div>
          <p className="mt-1 text-xs font-medium leading-5 text-on-surface-variant">
            Оценка учитывает только маршрут, граф и активные слои данных, которые вернул API.
          </p>
          <div className="mt-3">
            <DataLayerPills score={score} compact />
          </div>
        </div>
      </div>

      {reasons.length ? (
        <div className="mt-4 space-y-2" data-testid="score-reasons">
          {reasons.map((reason) => (
            <div key={`${reason.code}-${reason.value}-${reason.weight}`} className="score-reason-row">
              <span className="score-reason-dot" />
              <span className="min-w-0 flex-1 truncate">{reasonLabel(reason)}</span>
              <span className="text-outline">{reason.weight > 0 ? `${reason.weight > 0 ? "-" : ""}${Math.abs(reason.weight)}` : "+"}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-xs font-medium text-outline">Для этого маршрута нет дополнительных причин оценки.</p>
      )}
    </motion.section>
  );
}
