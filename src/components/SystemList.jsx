import { AlertTriangle, CheckCircle2, CircleOff } from "lucide-react";

import { cn } from "../lib/ui";

export function NativeSection({ title, eyebrow, children, className = "" }) {
  return (
    <section className={cn("native-section", className)}>
      {eyebrow ? <div className="native-section-eyebrow">{eyebrow}</div> : null}
      {title ? <div className="native-section-title">{title}</div> : null}
      <div className="native-section-body">{children}</div>
    </section>
  );
}

export function StatusRow({ icon: Icon, title, subtitle, meta, tone = "neutral", children }) {
  const ToneIcon = tone === "success" ? CheckCircle2 : tone === "warning" ? AlertTriangle : tone === "muted" ? CircleOff : null;

  return (
    <div className={cn("native-row", `native-row-${tone}`)}>
      <div className="native-row-leading">
        {Icon ? <Icon size={18} aria-hidden="true" /> : ToneIcon ? <ToneIcon size={18} aria-hidden="true" /> : null}
      </div>
      <div className="native-row-copy">
        <div className="native-row-title">{title}</div>
        {subtitle ? <div className="native-row-subtitle">{subtitle}</div> : null}
      </div>
      {meta ? <div className="native-row-meta">{meta}</div> : null}
      {children}
    </div>
  );
}
