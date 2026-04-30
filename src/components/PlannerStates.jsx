import { motion } from "framer-motion";
import { AlertTriangle, Loader2, Route, Search } from "lucide-react";

import { OVERLAY_TRANSITION } from "../config/safeRoute";

export function RouteLoadingState() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 6, scale: 0.995 }}
      transition={OVERLAY_TRANSITION}
      className="route-skeleton-stack"
    >
      {[0, 1].map((item) => (
        <div key={item} className="route-skeleton-card">
          <div className="route-skeleton-line w-2/5" />
          <div className="route-skeleton-line w-3/5" />
          <div className="mt-4 flex gap-2">
            <div className="route-skeleton-pill w-24" />
            <div className="route-skeleton-pill w-32" />
          </div>
        </div>
      ))}
      <div className="flex items-center justify-center gap-2 text-xs font-bold text-primary">
        <Loader2 size={15} className="animate-spin" />
        Считаем реальные варианты маршрута
      </div>
    </motion.div>
  );
}

export function RouteEmptyState() {
  return (
    <motion.div initial={{ opacity: 0, y: 8, scale: 0.99 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={OVERLAY_TRANSITION} className="material-card rounded-[1rem] px-5 py-5 text-sm text-on-surface-variant">
      <div className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-[0.8rem] bg-primary/10 text-primary">
        <Route size={20} />
      </div>
      <div className="text-base font-bold text-on-surface">Маршруты появятся здесь</div>
      <p className="mt-2 leading-6">Выберите место из подсказок поиска. SafeRoute покажет только реальные маршруты по графу Москвы.</p>
    </motion.div>
  );
}

export function SearchEmptyState() {
  return (
    <motion.div initial={{ opacity: 0, y: 8, scale: 0.99 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={OVERLAY_TRANSITION} className="material-card rounded-[1rem] px-5 py-5 text-sm text-on-surface-variant">
      <div className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-[0.8rem] bg-primary/10 text-primary">
        <Search size={20} />
      </div>
      <div className="text-base font-bold text-on-surface">Начните с поиска</div>
      <p className="mt-2 leading-6">Введите адрес или ориентир. Поиск, маршрут и оценка безопасности работают через локальный SafeRoute API.</p>
    </motion.div>
  );
}

export function ErrorRecoveryCard({ feedback, onRetry }) {
  if (feedback?.type !== "error") {
    return null;
  }

  return (
    <motion.div initial={{ opacity: 0, y: 8, scale: 0.99 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={OVERLAY_TRANSITION} className="error-recovery-card">
      <div className="flex items-start gap-3">
        <div className="error-recovery-icon">
          <AlertTriangle size={17} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-black text-on-surface">Не удалось построить маршрут</div>
          <p className="mt-1 text-xs font-medium leading-5 text-on-surface-variant">{feedback.message}</p>
          {onRetry ? (
            <button type="button" onClick={onRetry} className="mt-3 rounded-full bg-white/78 px-4 py-2 text-xs font-bold text-on-surface transition hover:bg-white">
              Повторить
            </button>
          ) : null}
        </div>
      </div>
    </motion.div>
  );
}
