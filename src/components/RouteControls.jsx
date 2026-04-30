import { motion } from "framer-motion";

import { PANEL_TRANSITION } from "../config/safeRoute";
import { cn } from "../lib/ui";

export function SegmentedControl({ label, options, value, onChange, compact = false }) {
  return (
    <fieldset className="segmented-control-group">
      <legend className="mb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-outline">{label}</legend>
      <div className={cn("segmented-control", compact ? "segmented-control-compact" : "")}>
        {options.map((option) => {
          const Icon = option.icon;
          const active = value === option.id;

          return (
            <button
              key={option.id}
              type="button"
              onClick={() => onChange(option.id)}
              className={cn("segmented-option", active ? "segmented-option-active" : "")}
              aria-pressed={active}
              title={option.description || option.label}
            >
              {active ? <motion.span layoutId={`${label}-active`} className="segmented-option-bg" transition={PANEL_TRANSITION} /> : null}
              <Icon size={compact ? 15 : 16} aria-hidden="true" />
              <span className="segmented-option-copy">
                <span className="segmented-option-label">{compact ? option.shortLabel || option.label : option.label}</span>
                {option.description && !compact ? <span className="segmented-option-description">{option.description}</span> : null}
              </span>
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
