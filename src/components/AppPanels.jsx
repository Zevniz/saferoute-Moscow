import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRightLeft,
  ArrowUp,
  CheckCircle2,
  Clock3,
  CloudSun,
  Compass,
  CornerUpLeft,
  CornerUpRight,
  Eye,
  EyeOff,
  ExternalLink,
  Layers as LayersIcon,
  Loader2,
  MapPinned,
  Menu,
  Navigation2,
  Radio,
  RotateCcw,
  Route,
  Search,
  ShieldCheck,
  Wifi,
  X,
} from "lucide-react";

import { APP_TABS, CARD_TRANSITION, FIGMA_DESIGN_URL, OVERLAY_TRANSITION, PANEL_TRANSITION, TAB_COPY } from "../config/safeRoute";
import { formatDistance, formatInstructionMeta, getArrivalTime } from "../lib/route-utils";
import { cn } from "../lib/ui";

function getHintIcon(title) {
  const normalized = title.toLowerCase();
  if (normalized.includes("налево") || normalized.includes("left")) {
    return CornerUpLeft;
  }

  if (normalized.includes("направо") || normalized.includes("right")) {
    return CornerUpRight;
  }

  return ArrowUp;
}

function topScoreReason(score) {
  const reasons = Array.isArray(score?.reasons) ? score.reasons : [];
  return reasons.find((reason) => reason?.code !== "safety_weight") ?? reasons[0] ?? null;
}

function formatScoreReason(reason) {
  if (!reason) {
    return null;
  }

  const labels = {
    safety_weight: "вес графа",
    walk_friendly_edges: "пешеходные участки",
    cycleway_edges: "велополоса",
    high_speed_or_lanes: "дорожная экспозиция",
    narrow_width: "узко",
    narrow_sidewalk_width: "узкий тротуар",
    medium_width: "средняя ширина",
    wide_width: "широкий участок",
    bad_surface: "покрытие",
    smooth_surface: "ровно",
    missing_sidewalk: "нет тротуара",
    curb_risk: "бордюры",
    many_crossings: "переходы",
    poor_lighting: "освещение",
    steep_slope: "уклон",
    low_traffic: "спокойная дорога",
    traffic_intensity: "измеренный трафик",
    road_exposure_proxy: "дорожная экспозиция",
    micromobility_forbidden: "запрет СИМ",
    forbidden_zone: "запретная зона",
    micromobility_slow_zone: "зона ограничения",
    telemetry_confidence: "телеметрия",
    good_lighting: "освещение",
    weather_sensitive_risk: "погода",
  };

  return labels[reason.code] ?? reason.code?.replaceAll("_", " ");
}

export function StatusBanner({ feedback, loading }) {
  if (!feedback && !loading) {
    return null;
  }

  const content = loading
    ? {
        type: "loading",
        message: "Подбираем реальные маршруты по Москве...",
      }
    : feedback;

  const tone = {
    error: "bg-error/10 text-on-error-container border-error/15",
    info: "bg-primary/10 text-primary border-primary/15",
    neutral: "bg-surface-container-lowest/90 text-on-surface-variant border-outline-variant/40",
    loading: "bg-primary/10 text-primary border-primary/15",
  }[content.type ?? "neutral"];
  const StatusIcon = loading ? Loader2 : content.type === "error" ? X : content.type === "info" ? CheckCircle2 : ShieldCheck;

  return (
    <motion.div
      key={content.message}
      initial={{ opacity: 0, y: 8, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 6, scale: 0.99 }}
      transition={OVERLAY_TRANSITION}
      className={cn(
        "mb-4 rounded-2xl border px-4 py-3 text-sm font-medium shadow-[0_10px_30px_rgba(0,88,188,0.06)]",
        tone,
      )}
    >
      <div className="flex items-center gap-2">
        <StatusIcon size={16} className={loading ? "animate-spin" : ""} aria-hidden="true" />
        <span>{content.message}</span>
      </div>
    </motion.div>
  );
}

export function ModeButton({ option, active, onSelect }) {
  const Icon = option.icon;

  return (
    <button
      type="button"
      onClick={() => onSelect(option.id)}
      className={cn(
        "relative flex flex-1 items-center justify-center rounded-full px-2 py-2.5 text-sm font-semibold transition-all duration-300 active:scale-[0.98]",
        active ? "bg-primary text-on-primary shadow-lg shadow-blue-500/30" : "text-on-surface-variant hover:bg-white/55",
      )}
      title={option.label}
    >
      <Icon size={16} />
    </button>
  );
}

export function SearchResults({ results, highlightedIndex, loading, query, onPick }) {
  const trimmedQuery = query.trim();
  const hasQuery = trimmedQuery.length >= 2;

  return (
    <AnimatePresence>
      {hasQuery ? (
        <motion.div
          initial={{ opacity: 0, y: -8, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -6, scale: 0.98 }}
          transition={OVERLAY_TRANSITION}
          className="absolute left-4 right-4 top-[82px] z-[60] mx-auto max-w-2xl overflow-hidden rounded-[1.6rem] border border-white/55 bg-white/88 shadow-[0_24px_70px_rgba(0,88,188,0.16)] backdrop-blur-3xl md:left-4 md:right-auto md:max-w-xl"
        >
          {loading ? (
            <div className="flex items-center gap-2 px-4 py-4 text-sm font-medium text-primary">
              <Loader2 size={16} className="animate-spin" />
              Ищем места через SafeRoute API...
            </div>
          ) : results.length ? (
            <div className="py-2">
              {results.map((result, index) => (
                <button
                  key={`${result.id}-${result.lat}-${result.lon}`}
                  type="button"
                  onMouseDown={(event) => {
                    event.preventDefault();
                    onPick(result);
                  }}
                  className={cn(
                    "search-result-row block w-full px-4 py-3 text-left transition-colors",
                    index === highlightedIndex ? "bg-primary/10" : "hover:bg-white/70",
                  )}
                >
                  <div className="truncate text-sm font-bold text-on-surface">{result.label}</div>
                  <div className="mt-1 text-xs font-medium uppercase tracking-[0.12em] text-outline">
                    {result.kind || "place"} • {Number(result.lat).toFixed(4)}, {Number(result.lon).toFixed(4)}
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="px-4 py-4 text-sm text-on-surface-variant">
              Ничего не найдено. Попробуйте уточнить адрес или ориентир в Москве.
            </div>
          )}
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

export function AppTabRail({ activeTab, onSelect }) {
  return (
    <nav className="app-tab-rail mb-5 grid grid-cols-3 gap-1 rounded-[1.15rem] p-1" aria-label="Разделы SafeRoute">
      {APP_TABS.map((tab) => {
        const Icon = tab.icon;
        const active = activeTab === tab.id;

        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onSelect(tab.id)}
            className={cn(
              "relative isolate flex min-w-0 flex-col items-center justify-center gap-1 rounded-[0.85rem] px-1.5 py-2.5 text-[10px] font-semibold transition-all duration-200 active:scale-[0.98] sm:text-[11px]",
              active ? "text-primary" : "text-on-surface-variant hover:text-on-surface",
            )}
            aria-current={active ? "page" : undefined}
            aria-label={tab.label}
            title={tab.label}
            data-motion-surface="tab"
          >
            {active ? (
              <motion.span
                layoutId="active-app-tab"
                className="absolute inset-0 -z-10 rounded-[0.85rem] bg-white shadow-[0_8px_18px_rgba(20,36,56,0.08)]"
                transition={PANEL_TRANSITION}
              />
            ) : null}
            <Icon size={16} />
            <span className="tab-label truncate">{tab.shortLabel ?? tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

export function PanelHeader({ activeTab, onClose }) {
  const copy = TAB_COPY[activeTab] ?? TAB_COPY.route;

  return (
    <div className="panel-header mb-5 flex items-start justify-between gap-3">
      <div>
        <motion.h1
          key={copy.title}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={OVERLAY_TRANSITION}
          className="panel-title text-on-surface"
        >
          {copy.title}
        </motion.h1>
        <motion.p
          key={copy.subtitle}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...OVERLAY_TRANSITION, delay: 0.03 }}
          className="panel-subtitle mt-1 max-w-[21rem] text-on-surface-variant"
        >
          {copy.subtitle}
        </motion.p>
      </div>
      <button
        type="button"
        onClick={onClose}
        className="icon-button inline-flex md:hidden"
        aria-label="Закрыть панель"
      >
        <X size={18} />
      </button>
    </div>
  );
}

function EndpointRow({ endpoint, label, value, tone, active, onSelect }) {
  const isOrigin = endpoint === "origin";

  return (
    <button
      type="button"
      onClick={() => onSelect(endpoint)}
      className={cn(
        "endpoint-row endpoint-row-action relative flex w-full items-center rounded-[1rem] px-4 py-4 text-left transition-all duration-200",
        active ? "endpoint-row-active" : "hover:bg-white",
      )}
      aria-pressed={active}
      aria-label={`${label}: ${value}`}
    >
      <span className="endpoint-marker-wrap mr-3">
        <span
          className={cn(
            "endpoint-marker",
            isOrigin ? "rounded-full bg-primary shadow-[0_0_0_5px_rgba(0,112,235,0.12)]" : "rounded-[5px] bg-error shadow-[0_0_0_5px_rgba(186,26,26,0.1)]",
          )}
        />
      </span>
      <span className="min-w-0 flex-1">
        <span className="endpoint-label block text-outline">{label}</span>
        <span className="mt-0.5 block truncate text-sm font-semibold text-on-surface">{value}</span>
      <span className={cn("mt-1 block text-xs font-medium", active ? "text-primary" : "text-outline")}>
          {active ? "Введите адрес сверху или поставьте точку на карте" : tone}
        </span>
      </span>
    </button>
  );
}

export function EndpointStack({ origin, destination, activeEndpoint = "destination", onSelectEndpoint, onSwap }) {
  return (
    <div className="endpoint-stack relative space-y-2">
      <div className="endpoint-rail" aria-hidden="true" />
      <EndpointRow
        endpoint="origin"
        label="Откуда"
        value={origin.label}
        tone="Нажмите, чтобы изменить старт"
        active={activeEndpoint === "origin"}
        onSelect={onSelectEndpoint}
      />
      <EndpointRow
        endpoint="destination"
        label="Куда"
        value={destination?.label ?? "Выберите точку назначения"}
        tone="Нажмите, чтобы выбрать финиш"
        active={activeEndpoint === "destination"}
        onSelect={onSelectEndpoint}
      />
      <button
        type="button"
        onClick={onSwap}
        className="icon-button absolute right-2 top-1/2 -translate-y-1/2 bg-white"
        aria-label="Поменять точки местами"
      >
        <ArrowRightLeft size={18} />
      </button>
    </div>
  );
}

export function EmptyState({ title, children, icon: Icon = Compass }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={OVERLAY_TRANSITION}
      className="material-card rounded-[1rem] px-5 py-5 text-sm text-on-surface-variant"
    >
      <div className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-[1.05rem] bg-primary/10 text-primary">
        <Icon size={20} />
      </div>
      <div className="text-base font-bold text-on-surface">{title}</div>
      <p className="mt-2 leading-6">{children}</p>
    </motion.div>
  );
}

export function ToggleRow({ icon: Icon, title, subtitle, enabled, onToggle }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="native-toggle-row group flex w-full items-center justify-between gap-4 rounded-[0.9rem] px-4 py-3.5 text-left transition-all hover:bg-white active:scale-[0.99]"
      aria-pressed={enabled}
    >
      <div className="flex min-w-0 items-center gap-3">
        <div className={cn("toggle-icon", enabled ? "text-primary" : "text-outline")}>
          <Icon size={18} />
        </div>
        <div className="min-w-0">
          <div className="text-sm font-bold text-on-surface">{title}</div>
          <div className="mt-1 text-xs font-medium leading-5 text-on-surface-variant">{subtitle}</div>
        </div>
      </div>
      <span className={cn("apple-switch", enabled ? "apple-switch-on" : "")}>
        <span />
      </span>
    </button>
  );
}

export function ServiceHealthList({ health, loading, onRefresh }) {
  const services = health?.services ?? {};
  const status = health?.status ?? "unknown";
  const statusText = status === "ok" ? "Все сервисы онлайн" : status === "degraded" ? "Есть проблемы" : "Статус неизвестен";

  return (
    <div className="space-y-4">
      <div className="material-card rounded-[1rem] px-5 py-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="native-section-eyebrow">Сервисы</div>
            <div className="mt-2 text-xl font-black tracking-tight text-on-surface">{statusText}</div>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            className="icon-button bg-white"
            aria-label="Обновить статус сервисов"
          >
            {loading ? <Loader2 size={18} className="animate-spin text-primary" /> : <Wifi size={18} />}
          </button>
        </div>
      </div>
      <div className="space-y-2">
        {["postgres", "photon", "valhalla"].map((name) => {
          const service = services[name];
          const isOk = service?.status === "ok";
          return (
            <div key={name} className="service-row flex items-center justify-between gap-3 rounded-[0.9rem] px-4 py-3">
              <div>
                <div className="text-sm font-bold capitalize text-on-surface">{name}</div>
                <div className="mt-0.5 text-xs font-medium text-outline">{service?.detail || service?.status || "не проверено"}</div>
              </div>
              <span className={cn("status-dot", isOk ? "status-dot-ok" : "status-dot-warn")} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function RouteCard({ route, index, isActive, onSelect }) {
  const score = route.properties?.score;
  const hasSafetyScore = score?.total != null;
  const scoreReason = topScoreReason(score);
  const scoreReasonLabel = formatScoreReason(scoreReason);
  const scoreTotal = typeof score?.total === "number" ? score.total : route.properties?.safety_index;
  const scoreTone = scoreTotal >= 85 ? "excellent" : scoreTotal >= 70 ? "good" : "caution";

  return (
    <motion.button
      type="button"
      layout
      initial={{ opacity: 0, x: -14 }}
      animate={{
        opacity: 1,
        x: 0,
        transition: { ...CARD_TRANSITION, delay: index * 0.035 },
      }}
      whileHover={{ y: -2 }}
      whileTap={{ scale: 0.988 }}
      transition={CARD_TRANSITION}
      onClick={() => onSelect(route.id)}
      aria-pressed={isActive}
      className={cn(
        "route-card material-card relative w-full overflow-hidden rounded-[1rem] px-4 py-4 text-left",
        isActive ? "route-card-active" : "hover:bg-white",
      )}
    >
      <AnimatePresence>
        {isActive ? <motion.div layoutId="route-beacon" className="absolute inset-y-4 left-0 w-1 rounded-full bg-primary" transition={CARD_TRANSITION} /> : null}
      </AnimatePresence>
      <div className="route-card-head">
        <div className="route-card-title-wrap">
          <span className={cn("route-number", isActive ? "route-number-active" : "")}>{index + 1}</span>
          <div className="min-w-0">
            <div className="route-title">{route.label}</div>
            {scoreReasonLabel ? <div className="route-top-reason">{scoreReasonLabel}</div> : null}
          </div>
        </div>

        {hasSafetyScore ? (
          <div className={cn("route-score-pill", `route-score-pill-${scoreTone}`)}>
            <span>{scoreTotal ?? "--"}</span>
            <small>/100</small>
          </div>
        ) : null}
      </div>

      <div className="route-card-metrics">
        <span>
          <Clock3 size={14} aria-hidden="true" />
          {route.properties?.estimated_mins ?? "--"} мин
        </span>
        <span>
          <MapPinned size={14} aria-hidden="true" />
          {formatDistance(route.properties?.distance_m)}
        </span>
      </div>

      <p className="route-card-description">{route.subtitle}</p>

      <div className="route-card-footer">
        <div className="route-score-copy">{hasSafetyScore ? `Оценка ${scoreTotal}/100` : "Оценка появится после расчёта"}</div>
      </div>
    </motion.button>
  );
}

export function NavigationInstructionCard({ hint, gpsStatus, rerouting, onOpenPlanner }) {
  const Icon = getHintIcon(hint.title);

  return (
    <motion.div
      initial={{ opacity: 0, y: -16, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -8, scale: 0.99 }}
      transition={OVERLAY_TRANSITION}
      className="top-instruction-shell pointer-events-none fixed left-0 right-0 top-0 z-50 flex justify-center px-4 pt-6 md:pt-8"
    >
      <div className="top-instruction pointer-events-auto flex w-full max-w-2xl items-center gap-4 rounded-[1.5rem] px-4 py-4">
        <button
          type="button"
          onClick={onOpenPlanner}
          className="inline-flex h-12 w-12 items-center justify-center rounded-full text-on-surface transition-all hover:bg-white/55 active:scale-95"
          aria-label="Открыть навигационное меню"
        >
          <Menu size={20} />
        </button>
        <div className="inline-flex h-16 w-16 items-center justify-center rounded-[1rem] soul-gradient text-on-primary shadow-[0_12px_26px_rgba(0,88,188,0.2)]">
          {rerouting ? <Loader2 size={28} className="animate-spin" /> : <Icon size={28} />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-xl font-black tracking-tight text-on-surface md:text-[1.7rem]">
            {rerouting ? "Перестраиваем маршрут" : hint.title}
          </div>
          <div className="mt-1 truncate text-sm font-medium text-on-surface-variant md:text-base">
            {gpsStatus || hint.subtitle}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export function TripSheet({ route, livePosition, activeInstructionIndex, onShowPlanner, onReset }) {
  const instructions = route.properties?.instructions ?? [];
  const activeInstruction = instructions[activeInstructionIndex] ?? instructions[0] ?? null;
  const instructionMeta = activeInstruction ? formatInstructionMeta(activeInstruction) : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 22, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 14, scale: 0.99 }}
      transition={OVERLAY_TRANSITION}
      className="fixed bottom-0 left-0 right-0 z-50 flex justify-center px-4 pb-6 md:pb-8"
    >
      <div className="trip-sheet pointer-events-auto grid w-full max-w-3xl grid-cols-[minmax(0,1fr)_auto] items-center gap-4 rounded-[1.5rem] px-5 py-5">
        <div className="trip-sheet-copy min-w-0">
          <div className="trip-sheet-time text-3xl font-black tracking-tight text-primary">{getArrivalTime(route.properties?.estimated_mins ?? 0)}</div>
          <div className="trip-sheet-meta mt-1 text-sm font-medium text-on-surface-variant md:text-base">
            Осталось {route.properties?.estimated_mins ?? "--"} мин • {formatDistance(route.properties?.distance_m)}
          </div>
          {activeInstruction ? (
            <div className="trip-sheet-next mt-3">
              <div className="truncate text-sm font-black text-on-surface">{activeInstruction.text}</div>
              <div className="mt-1 text-xs font-medium text-outline">
                {instructionMeta}
                {` • Шаг ${Math.min(activeInstructionIndex + 1, instructions.length || 1)} из ${instructions.length || 1}`}
                {livePosition?.accuracy ? ` • GPS ±${Math.round(livePosition.accuracy)} м` : ""}
              </div>
            </div>
          ) : null}
        </div>
        <div className="trip-sheet-actions flex shrink-0 items-center gap-3">
          <button
            type="button"
            onClick={onShowPlanner}
            className="inline-flex h-14 w-14 items-center justify-center rounded-full bg-white/68 text-on-surface shadow-[0_6px_18px_rgba(0,0,0,0.06)] transition-all hover:bg-white/82 active:scale-95"
            aria-label="Показать навигационное меню"
          >
            <Route size={22} />
          </button>
          <button
            type="button"
            onClick={onReset}
            className="rounded-full bg-error px-7 py-4 text-sm font-bold tracking-[0.12em] text-on-error shadow-[0_12px_28px_rgba(186,26,26,0.2)] transition-all hover:opacity-92 active:scale-95"
          >
            Завершить
          </button>
        </div>
      </div>
    </motion.div>
  );
}

export function WeatherChip({ route }) {
  const weather = route?.properties?.score?.data_sources?.weather;
  const weatherActive = Boolean(weather?.active);
  const Icon = weatherActive ? CloudSun : ShieldCheck;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ ...OVERLAY_TRANSITION, delay: 0.12 }}
      className="pointer-events-none fixed bottom-4 right-4 z-30 hidden sm:block md:bottom-6 md:right-6 md:z-40"
    >
      <div className="material-toolbar pointer-events-none flex items-center gap-3 rounded-[1.25rem] px-4 py-3">
        <Icon className="text-primary" size={22} />
        <div>
          <div className="text-base font-black leading-none text-on-surface">{weatherActive ? "Погода" : "Публичная бета"}</div>
          <div className="mt-1 text-xs font-medium text-on-surface-variant">
            {weatherActive ? "Open-Meteo активен" : "OSM и переходы"}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export { CheckCircle2, Compass, Eye, EyeOff, LayersIcon, Loader2, Navigation2, Radio, RotateCcw, Route, Search, ShieldCheck };
