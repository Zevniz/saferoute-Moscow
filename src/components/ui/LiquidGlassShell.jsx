import { useReducedMotion } from "framer-motion";

import { cn } from "../../lib/ui";

export function LiquidGlassShell({
  as: Component = "div",
  variant = "card",
  tone = "neutral",
  interactive = false,
  disabled = false,
  className,
  children,
  ...props
}) {
  const reducedMotion = useReducedMotion();

  return (
    <Component
      className={cn(
        "liquid-glass-shell",
        `liquid-glass-${variant}`,
        `liquid-glass-tone-${tone}`,
        interactive && "liquid-glass-interactive",
        disabled && "liquid-glass-disabled",
        className,
      )}
      data-liquid-glass={variant}
      data-liquid-tone={tone}
      data-liquid-native={reducedMotion || disabled ? "fallback" : "css"}
      disabled={Component === "button" ? disabled : undefined}
      {...props}
    >
      <span className="liquid-glass-content">{children}</span>
    </Component>
  );
}
