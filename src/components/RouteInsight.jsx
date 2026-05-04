import { useState } from "react";
import { motion } from "framer-motion";
import { AlertCircle, CheckCircle2, HeartHandshake, Info, MessageSquare, Moon, ShieldCheck, Sparkles } from "lucide-react";

import { OVERLAY_TRANSITION } from "../config/safeRoute";
import { getRouteConfidence, getRouteInsight, getRouteKnowledge, getRouteTimeline } from "../lib/route-utils";
import { formatCrossingSummary, getCrossingSafetyDescription, getCrossingIcon } from "../lib/crossing-utils";
import { cn } from "../lib/ui";

const FEEDBACK_OPTIONS = [
  { id: "safe", label: "Было спокойно" },
  { id: "issue", label: "Есть проблемный участок" },
  { id: "data", label: "Данные неточны" },
];

function confidenceToneClass(tone) {
  return {
    positive: "insight-meter-positive",
    caution: "insight-meter-caution",
    neutral: "insight-meter-neutral",
  }[tone ?? "neutral"];
}

export function RouteInsightPanel({ route, routes }) {
  if (!route) {
    return null;
  }

  const insight = getRouteInsight(route, routes);
  const timeline = getRouteTimeline(route);
  const confidence = getRouteConfidence(route);
  const knowledge = getRouteKnowledge(route);
  const scoreTotal = route?.properties?.score?.total ?? route?.properties?.safety_index ?? null;

  return (
    <motion.section
      initial={{ opacity: 0, y: 8, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={OVERLAY_TRANSITION}
      className="route-insight-panel"
      aria-label="Почему выбран этот маршрут и какие данные ограничены"
    >
      <div className="insight-hero">
        <div className="insight-hero-icon">
          <Sparkles size={18} aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="insight-kicker">Почему этот маршрут</div>
          <p className="insight-brief">{insight.brief}</p>
          <p className="insight-comparison">{insight.comparison}</p>
          <p className="insight-limitation">{insight.limitation}</p>
        </div>
      </div>

      <div className="trust-concepts-grid" aria-label="Как читать оценку маршрута">
        <div className="trust-concept-card">
          <span>Оценка маршрута</span>
          <strong>{scoreTotal == null ? "--" : `${scoreTotal}/100`}</strong>
          <p>Сравнительный балл по доступным факторам, не гарантия безопасности.</p>
        </div>
        <div className="trust-concept-card">
          <span>Уверенность данных</span>
          <strong>{confidence.value == null ? confidence.label : `${confidence.label} · ${confidence.value}%`}</strong>
          <p>{confidence.caveat}</p>
        </div>
        <div className="trust-concept-card">
          <span>Приоритет маршрута</span>
          <strong>{route.label}</strong>
          <p>{route.subtitle ?? "Выбранный режим влияет на баланс времени и спокойствия."}</p>
        </div>
        <div className="trust-concept-card trust-concept-card-caution">
          <span>Неизвестные риски</span>
          <strong>{knowledge.unknown.length}</strong>
          <p>Эти факторы не подменяются и не считаются безопасными.</p>
        </div>
      </div>

      <div className="insight-grid">
        <div className="insight-meter-card">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="insight-card-title">Покрытие данных</div>
              <div className="insight-card-subtitle">{confidence.description}</div>
            </div>
            <div className={cn("insight-meter", confidenceToneClass(confidence.tone))}>
              <span>{confidence.value ?? "--"}</span>
              <small>{confidence.value == null ? "" : "%"}</small>
            </div>
          </div>
          <div className="insight-meter-track" aria-hidden="true">
            <span style={{ width: `${confidence.value ?? 0}%` }} />
          </div>
        </div>

        <div className="insight-privacy-card">
          <ShieldCheck size={18} aria-hidden="true" />
          <div>
            <div className="insight-card-title">Без скрытой подмены</div>
            <p className="insight-card-subtitle">
              Отсутствующие слои не считаются безопасными и не превращаются в причины оценки.
            </p>
          </div>
        </div>
      </div>

      <div className="route-knowledge-grid" aria-label="Что известно и что неизвестно по маршруту">
        <div className="route-knowledge-card">
          <div className="route-knowledge-title">
            <CheckCircle2 size={15} aria-hidden="true" />
            <span>Что мы знаем</span>
          </div>
          <ul>
            {knowledge.known.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div className="route-knowledge-card route-knowledge-card-muted">
          <div className="route-knowledge-title">
            <AlertCircle size={15} aria-hidden="true" />
            <span>Что мы не знаем</span>
          </div>
          <ul>
            {knowledge.unknown.slice(0, 5).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p>{knowledge.note}</p>
        </div>
      </div>

      <div className="route-timeline" aria-label="Что ожидать по маршруту">
        <div className="route-timeline-title">
          <Moon size={16} aria-hidden="true" />
          <span>Что по пути по доступным данным</span>
        </div>
        <p className="route-timeline-note">Это краткая выжимка из причин оценки и манёвров, а не точная карта каждого участка.</p>
        <div className="route-timeline-list">
          {timeline.map((item) => (
            <div key={item.id} className={cn("route-timeline-item", `route-timeline-${item.tone}`)}>
              <span className="route-timeline-dot" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <div className="route-timeline-item-title">{item.title}</div>
                <p className="route-timeline-item-copy">{item.description}</p>
              </div>
              <span className="route-timeline-meta">{item.meta}</span>
            </div>
          ))}
        </div>
      </div>

      <LocalFeedbackPanel />
    </motion.section>
  );
}

export function LocalFeedbackPanel() {
  const [selected, setSelected] = useState(null);
  const selectedOption = FEEDBACK_OPTIONS.find((option) => option.id === selected);

  return (
    <div className="local-feedback-panel" aria-label="Локальная заметка о маршруте">
      <div className="flex items-start gap-3">
        <div className="local-feedback-icon">
          {selected ? <CheckCircle2 size={17} aria-hidden="true" /> : <MessageSquare size={17} aria-hidden="true" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="insight-card-title">Заметка о маршруте</div>
          <p className="insight-card-subtitle">
            Сохраняется только в интерфейсе этой сессии. Сейчас не отправляется, не создаёт телеметрию и не влияет на маршруты.
          </p>
          <div className="local-feedback-actions">
            {FEEDBACK_OPTIONS.map((option) => (
              <button
                key={option.id}
                type="button"
                onClick={() => setSelected(option.id)}
                className={cn("local-feedback-chip", selected === option.id ? "local-feedback-chip-active" : "")}
                aria-pressed={selected === option.id}
              >
                {option.label}
              </button>
            ))}
          </div>
          {selectedOption ? (
            <div className="local-feedback-result">
              <HeartHandshake size={14} aria-hidden="true" />
              <span>Заметка выбрана: «{selectedOption.label}». Она останется локальной до перезагрузки страницы.</span>
            </div>
          ) : (
            <div className="local-feedback-result local-feedback-result-muted">
              <Info size={14} aria-hidden="true" />
              <span>Отправка может появиться только после отдельного согласия и privacy review.</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
