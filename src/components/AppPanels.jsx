import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRightLeft,
  ArrowUp,
  CheckCircle2,
  CloudSun,
  Compass,
  CornerUpLeft,
  CornerUpRight,
  Eye,
  EyeOff,
  ExternalLink,
  Layers as LayersIcon,
  Loader2,
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

import { APP_TABS, FIGMA_DESIGN_URL, OVERLAY_TRANSITION, PANEL_TRANSITION, TAB_COPY } from "../config/safeRoute";
import { formatCalories, formatDistance, getArrivalTime } from "../lib/route-utils";
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

  return (
    <motion.div
      key={content.message}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 6 }}
      transition={OVERLAY_TRANSITION}
      className={cn(
        "mb-4 rounded-2xl border px-4 py-3 text-sm font-medium shadow-[0_10px_30px_rgba(0,88,188,0.06)]",
        tone,
      )}
    >
      <div className="flex items-center gap-2">
        {loading ? <Loader2 size={16} className="animate-spin" /> : null}
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
                    "block w-full px-4 py-3 text-left transition-colors",
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

export function AppTabRail({ activeTab, hasRoute, onSelect }) {
  return (
    <nav className="app-tab-rail mb-6 grid grid-cols-5 gap-1 rounded-[1.35rem] p-1" aria-label="Разделы SafeRoute">
      {APP_TABS.map((tab) => {
        const Icon = tab.icon;
        const active = activeTab === tab.id;
        const isNavigationPending = tab.id === "navigation" && !hasRoute;

        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onSelect(tab.id)}
            className={cn(
              "relative isolate flex min-w-0 flex-col items-center justify-center gap-1 rounded-[1.05rem] px-1.5 py-2.5 text-[10px] font-semibold tracking-[-0.035em] transition-all duration-300 active:scale-[0.98] sm:text-[11px]",
              active ? "text-primary" : "text-on-surface-variant hover:text-on-surface",
              isNavigationPending && !active ? "opacity-60" : "",
            )}
            aria-current={active ? "page" : undefined}
            aria-label={tab.label}
            title={tab.label}
          >
            {active ? (
              <motion.span
                layoutId="active-app-tab"
                className="absolute inset-0 -z-10 rounded-[1.05rem] bg-white/82 shadow-[0_10px_24px_rgba(0,88,188,0.1)]"
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
  const copy = TAB_COPY[activeTab] ?? TAB_COPY.routes;

  return (
    <div className="mb-5 flex items-start justify-between gap-3">
      <div>
        <motion.h1
          key={copy.title}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={OVERLAY_TRANSITION}
          className="text-[1.55rem] font-black tracking-[-0.045em] text-on-surface"
        >
          {copy.title}
        </motion.h1>
        <motion.p
          key={copy.subtitle}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...OVERLAY_TRANSITION, delay: 0.03 }}
          className="mt-1 max-w-[21rem] text-sm font-medium leading-5 text-on-surface-variant"
        >
          {copy.subtitle}
        </motion.p>
      </div>
      <button
        type="button"
        onClick={onClose}
        className="inline-flex h-10 w-10 items-center justify-center rounded-full text-on-surface-variant transition-all hover:bg-white/55 md:hidden"
        aria-label="Закрыть панель"
      >
        <X size={18} />
      </button>
    </div>
  );
}

export function EndpointStack({ origin, destination, onSwap }) {
  return (
    <div className="endpoint-stack relative space-y-3">
      <div className="absolute bottom-5 left-4 top-5 w-px bg-outline-variant/30" />
      <div className="endpoint-row relative flex items-center rounded-[1.35rem] px-4 py-4">
        <div className="mr-3 h-3 w-3 rounded-full bg-primary shadow-[0_0_10px_rgba(0,88,188,0.38)]" />
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-outline">Откуда</div>
          <div className="truncate text-sm font-semibold text-on-surface">{origin.label}</div>
        </div>
      </div>
      <div className="endpoint-row relative flex items-center rounded-[1.35rem] px-4 py-4">
        <div className="mr-3 h-3 w-3 rounded-[4px] bg-error" />
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-outline">Куда</div>
          <div className="truncate text-sm font-semibold text-on-surface">
            {destination?.label ?? "Выберите точку назначения"}
          </div>
        </div>
      </div>
      <button
        type="button"
        onClick={onSwap}
        className="absolute right-2 top-1/2 inline-flex h-12 w-12 -translate-y-1/2 items-center justify-center rounded-full bg-white/88 text-on-surface-variant shadow-[0_10px_24px_rgba(0,0,0,0.08)] transition-all hover:bg-white active:scale-95"
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
      className="quiet-panel rounded-[1.55rem] px-5 py-5 text-sm text-on-surface-variant"
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
      className="toggle-row group flex w-full items-center justify-between gap-4 rounded-[1.4rem] px-4 py-4 text-left transition-all hover:bg-white/58 active:scale-[0.99]"
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
      <div className="quiet-panel rounded-[1.55rem] px-5 py-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-outline">Runtime health</div>
            <div className="mt-2 text-xl font-black tracking-tight text-on-surface">{statusText}</div>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-white/70 text-on-surface-variant transition-all hover:bg-white active:scale-95"
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
            <div key={name} className="service-row flex items-center justify-between gap-3 rounded-[1.2rem] px-4 py-3">
              <div>
                <div className="text-sm font-bold capitalize text-on-surface">{name}</div>
                <div className="mt-0.5 text-xs font-medium text-outline">{service?.detail || service?.status || "not checked"}</div>
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
  const calories = formatCalories(route.properties?.calories_burn);

  return (
    <motion.button
      type="button"
      layout
      initial={{ opacity: 0, x: -14 }}
      animate={{
        opacity: 1,
        x: 0,
        transition: { delay: index * 0.04, duration: 0.26, ease: [0.22, 1, 0.36, 1] },
      }}
      onClick={() => onSelect(route.id)}
      className={cn(
        "route-card relative w-full overflow-hidden rounded-[1.7rem] px-4 py-4 text-left",
        isActive ? "route-card-active bg-white/92 shadow-[0_18px_40px_rgba(0,88,188,0.14)]" : "bg-white/58 hover:bg-white/72",
      )}
    >
      <AnimatePresence>
        {isActive ? <motion.div layoutId="route-beacon" className="absolute inset-y-4 left-0 w-1 rounded-full bg-primary" /> : null}
      </AnimatePresence>
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className={cn("text-xl font-black tracking-tight", isActive ? "text-on-surface" : "text-on-surface-variant")}>
            {route.properties?.estimated_mins ?? "--"} мин
          </div>
          <div className={cn("mt-1 text-xs font-semibold uppercase tracking-[0.18em]", isActive ? "text-primary" : "text-outline")}>
            {route.label}
          </div>
        </div>
        <div className="text-right">
          <div className="text-sm font-semibold text-on-surface-variant">{formatDistance(route.properties?.distance_m)}</div>
          <div className="mt-2 text-xs text-outline">Safety {route.properties?.safety_index ?? "--"}%</div>
        </div>
      </div>
      <p className={cn("mt-2 text-sm", isActive ? "text-on-surface-variant" : "text-outline")}>{route.subtitle}</p>
      <div className="mt-3 flex items-center gap-3 text-xs text-on-surface-variant">
        <span>{route.properties?.source?.includes("valhalla") ? "Turn-by-turn" : "SafeRoute safety graph"}</span>
        {calories ? <span>{calories}</span> : null}
      </div>
    </motion.button>
  );
}

export function NavigationInstructionCard({ hint, gpsStatus, rerouting, onOpenPlanner }) {
  const Icon = getHintIcon(hint.title);

  return (
    <motion.div
      initial={{ opacity: 0, y: -16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={OVERLAY_TRANSITION}
      className="fixed left-0 right-0 top-0 z-50 flex justify-center px-4 pt-6 md:pt-8"
    >
      <div className="top-instruction pointer-events-auto flex w-full max-w-2xl items-center gap-4 rounded-[1.75rem] px-4 py-4">
        <button
          type="button"
          onClick={onOpenPlanner}
          className="inline-flex h-12 w-12 items-center justify-center rounded-full text-on-surface transition-all hover:bg-white/55 active:scale-95"
          aria-label="Открыть маршруты"
        >
          <Menu size={20} />
        </button>
        <div className="inline-flex h-16 w-16 items-center justify-center rounded-[1.4rem] soul-gradient text-on-primary shadow-[0_14px_30px_rgba(0,88,188,0.28)]">
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

  return (
    <motion.div
      initial={{ opacity: 0, y: 22 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 14 }}
      transition={OVERLAY_TRANSITION}
      className="fixed bottom-0 left-0 right-0 z-50 flex justify-center px-4 pb-6 md:pb-8"
    >
      <div className="trip-sheet pointer-events-auto flex w-full max-w-3xl items-center justify-between gap-4 rounded-[1.8rem] px-5 py-5">
        <div className="min-w-0">
          <div className="text-3xl font-black tracking-tight text-primary">{getArrivalTime(route.properties?.estimated_mins ?? 0)}</div>
          <div className="mt-1 text-sm font-medium text-on-surface-variant md:text-base">
            {route.properties?.estimated_mins ?? "--"} мин • {formatDistance(route.properties?.distance_m)}
          </div>
          <div className="mt-1 text-xs font-medium text-outline">
            Манёвр {Math.min(activeInstructionIndex + 1, instructions.length || 1)} из {instructions.length || 1}
            {livePosition?.accuracy ? ` • GPS ±${Math.round(livePosition.accuracy)} м` : ""}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <button
            type="button"
            onClick={onShowPlanner}
            className="inline-flex h-14 w-14 items-center justify-center rounded-full bg-white/68 text-on-surface shadow-[0_6px_18px_rgba(0,0,0,0.06)] transition-all hover:bg-white/82 active:scale-95"
            aria-label="Показать варианты маршрута"
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

export function WeatherChip() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.16 }}
      className="fixed bottom-6 right-6 z-40"
    >
      <div className="glass-panel pointer-events-none flex items-center gap-4 rounded-[1.6rem] px-4 py-3 shadow-[0_18px_44px_rgba(0,88,188,0.1)]">
        <CloudSun className="text-primary" size={28} />
        <div>
          <div className="text-xl font-black leading-none text-on-surface">Москва</div>
          <div className="mt-1 text-xs font-medium text-on-surface-variant">Статус маршрута</div>
        </div>
      </div>
    </motion.div>
  );
}

export { CheckCircle2, Compass, Eye, EyeOff, LayersIcon, Loader2, Navigation2, Radio, RotateCcw, Route, Search, ShieldCheck };
